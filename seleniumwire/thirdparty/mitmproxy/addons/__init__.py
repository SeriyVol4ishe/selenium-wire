from seleniumwire.thirdparty.mitmproxy.addons import anticache
from seleniumwire.thirdparty.mitmproxy.addons import anticomp
from seleniumwire.thirdparty.mitmproxy.addons import block
from seleniumwire.thirdparty.mitmproxy.addons import browser
from seleniumwire.thirdparty.mitmproxy.addons import check_ca
from seleniumwire.thirdparty.mitmproxy.addons import clientplayback
from seleniumwire.thirdparty.mitmproxy.addons import command_history
from seleniumwire.thirdparty.mitmproxy.addons import core
from seleniumwire.thirdparty.mitmproxy.addons import cut
from seleniumwire.thirdparty.mitmproxy.addons import disable_h2c
from seleniumwire.thirdparty.mitmproxy.addons import export
from seleniumwire.thirdparty.mitmproxy.addons import onboarding
from seleniumwire.thirdparty.mitmproxy.addons import proxyauth
from seleniumwire.thirdparty.mitmproxy.addons import script
from seleniumwire.thirdparty.mitmproxy.addons import serverplayback
from seleniumwire.thirdparty.mitmproxy.addons import mapremote
from seleniumwire.thirdparty.mitmproxy.addons import maplocal
from seleniumwire.thirdparty.mitmproxy.addons import modifybody
from seleniumwire.thirdparty.mitmproxy.addons import modifyheaders
from seleniumwire.thirdparty.mitmproxy.addons import stickyauth
from seleniumwire.thirdparty.mitmproxy.addons import stickycookie
from seleniumwire.thirdparty.mitmproxy.addons import streambodies
from seleniumwire.thirdparty.mitmproxy.addons import save
from seleniumwire.thirdparty.mitmproxy.addons import upstream_auth


def default_addons():
    return [
        core.Core(),
        browser.Browser(),
        block.Block(),
        anticache.AntiCache(),
        anticomp.AntiComp(),
        check_ca.CheckCA(),
        clientplayback.ClientPlayback(),
        command_history.CommandHistory(),
        cut.Cut(),
        disable_h2c.DisableH2C(),
        export.Export(),
        onboarding.Onboarding(),
        proxyauth.ProxyAuth(),
        script.ScriptLoader(),
        serverplayback.ServerPlayback(),
        mapremote.MapRemote(),
        maplocal.MapLocal(),
        modifybody.ModifyBody(),
        modifyheaders.ModifyHeaders(),
        stickyauth.StickyAuth(),
        stickycookie.StickyCookie(),
        streambodies.StreamBodies(),
        save.Save(),
        upstream_auth.UpstreamAuth(),
    ]
