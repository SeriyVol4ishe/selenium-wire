import queue
import threading
import time
import typing

import seleniumwire.thirdparty.mitmproxy.types
from seleniumwire.thirdparty.mitmproxy import command
from seleniumwire.thirdparty.mitmproxy import connections
from seleniumwire.thirdparty.mitmproxy import controller
from seleniumwire.thirdparty.mitmproxy import ctx
from seleniumwire.thirdparty.mitmproxy import exceptions
from seleniumwire.thirdparty.mitmproxy import flow
from seleniumwire.thirdparty.mitmproxy import http
from seleniumwire.thirdparty.mitmproxy import io
from seleniumwire.thirdparty.mitmproxy import log
from seleniumwire.thirdparty.mitmproxy import options
from seleniumwire.thirdparty.mitmproxy.coretypes import basethread
from seleniumwire.thirdparty.mitmproxy.net import server_spec, tls
from seleniumwire.thirdparty.mitmproxy.net.http import http1
from seleniumwire.thirdparty.mitmproxy.net.http.url import hostport
from seleniumwire.thirdparty.mitmproxy.utils import human


class RequestReplayThread(basethread.BaseThread):
    daemon = True

    def __init__(
            self,
            opts: options.Options,
            channel: controller.Channel,
            queue: queue.Queue,
    ) -> None:
        self.options = opts
        self.channel = channel
        self.queue = queue
        self.inflight = threading.Event()
        super().__init__("RequestReplayThread")

    def run(self):
        while True:
            f = self.queue.get()
            self.inflight.set()
            self.replay(f)
            self.inflight.clear()

    def replay(self, f):  # pragma: no cover
        f.live = True
        r = f.request
        bsl = human.parse_size(self.options.body_size_limit)
        authority_backup = r.authority
        server = None
        try:
            f.response = None

            # If we have a channel, run script hooks.
            request_reply = self.channel.ask("request", f)
            if isinstance(request_reply, http.HTTPResponse):
                f.response = request_reply

            if not f.response:
                # In all modes, we directly connect to the server displayed
                if self.options.mode.startswith("upstream:"):
                    server_address = server_spec.parse_with_mode(self.options.mode)[1].address
                    server = connections.ServerConnection(server_address)
                    server.connect()
                    if r.scheme == "https":
                        connect_request = http.make_connect_request((r.data.host, r.port))
                        server.wfile.write(http1.assemble_request(connect_request))
                        server.wfile.flush()
                        resp = http1.read_response(
                            server.rfile,
                            connect_request,
                            body_size_limit=bsl
                        )
                        if resp.status_code != 200:
                            raise exceptions.ReplayException(
                                "Upstream server refuses CONNECT request"
                            )
                        server.establish_tls(
                            sni=f.server_conn.sni,
                            **tls.client_arguments_from_options(self.options)
                        )
                        r.authority = b""
                    else:
                        r.authority = hostport(r.scheme, r.host, r.port)
                else:
                    server_address = (r.host, r.port)
                    server = connections.ServerConnection(server_address)
                    server.connect()
                    if r.scheme == "https":
                        server.establish_tls(
                            sni=f.server_conn.sni,
                            **tls.client_arguments_from_options(self.options)
                        )
                    r.authority = ""

                server.wfile.write(http1.assemble_request(r))
                server.wfile.flush()
                r.timestamp_start = r.timestamp_end = time.time()

                if f.server_conn:
                    f.server_conn.close()
                f.server_conn = server

                f.response = http1.read_response(server.rfile, r, body_size_limit=bsl)
            response_reply = self.channel.ask("response", f)
            if response_reply == exceptions.Kill:
                raise exceptions.Kill()
        except (exceptions.ReplayException, exceptions.NetlibException) as e:
            f.error = flow.Error(str(e))
            self.channel.ask("error", f)
        except exceptions.Kill:
            self.channel.tell("log", log.LogEntry(flow.Error.KILLED_MESSAGE, "info"))
        except Exception as e:
            self.channel.tell("log", log.LogEntry(repr(e), "error"))
        finally:
            r.authority = authority_backup
            f.live = False
            if server and server.connected():
                server.finish()
                server.close()


class ClientPlayback:
    def __init__(self):
        self.q = queue.Queue()
        self.thread: RequestReplayThread = None

    def check(self, f: flow.Flow):
        if f.live:
            return "Can't replay live flow."
        if f.intercepted:
            return "Can't replay intercepted flow."
        if isinstance(f, http.HTTPFlow):
            if not f.request:
                return "Can't replay flow with missing request."
            if f.request.raw_content is None:
                return "Can't replay flow with missing content."
        else:
            return "Can only replay HTTP flows."

    def load(self, loader):
        loader.add_option(
            "client_replay", typing.Sequence[str], [],
            "Replay client requests from a saved file."
        )

    def running(self):
        self.thread = RequestReplayThread(
            ctx.options,
            ctx.master.channel,
            self.q,
        )
        self.thread.start()

    def configure(self, updated):
        if "client_replay" in updated and ctx.options.client_replay:
            try:
                flows = io.read_flows_from_paths(ctx.options.client_replay)
            except exceptions.FlowReadException as e:
                raise exceptions.OptionsError(str(e))
            self.start_replay(flows)

    @command.command("replay.client.count")
    def count(self) -> int:
        """
            Approximate number of flows queued for replay.
        """
        inflight = 1 if self.thread and self.thread.inflight.is_set() else 0
        return self.q.qsize() + inflight

    @command.command("replay.client.stop")
    def stop_replay(self) -> None:
        """
            Clear the replay queue.
        """
        with self.q.mutex:
            lst = list(self.q.queue)
            self.q.queue.clear()
            for f in lst:
                f.revert()
        ctx.master.addons.trigger("update", lst)
        ctx.log.alert("Client replay queue cleared.")

    @command.command("replay.client")
    def start_replay(self, flows: typing.Sequence[flow.Flow]) -> None:
        """
            Add flows to the replay queue, skipping flows that can't be replayed.
        """
        lst = []
        for f in flows:
            hf = typing.cast(http.HTTPFlow, f)

            err = self.check(hf)
            if err:
                ctx.log.warn(err)
                continue

            lst.append(hf)
            # Prepare the flow for replay
            hf.backup()
            hf.is_replay = "request"
            hf.response = None
            hf.error = None
            # https://github.com/mitmproxy/mitmproxy/issues/2197
            if hf.request.http_version == "HTTP/2.0":
                hf.request.http_version = "HTTP/1.1"
                hf.request.headers.pop(":authority", None)
                host = hf.request.host
                if host is not None:
                    hf.request.headers.insert(0, "host", host)
            self.q.put(hf)
        ctx.master.addons.trigger("update", lst)

    @command.command("replay.client.file")
    def load_file(self, path: seleniumwire.thirdparty.mitmproxy.types.Path) -> None:
        """
            Load flows from file, and add them to the replay queue.
        """
        try:
            flows = io.read_flows_from_paths([path])
        except exceptions.FlowReadException as e:
            raise exceptions.CommandError(str(e))
        self.start_replay(flows)
