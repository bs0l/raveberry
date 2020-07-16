"""This module handles requests for the network info page."""

from __future__ import annotations

import io
import subprocess
from typing import Any, TYPE_CHECKING, Dict

import qrcode
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import render, redirect

from core.state_handler import Stateful

if TYPE_CHECKING:
    from core.base import Base


class NetworkInfo(Stateful):
    """This class handles requests on the /pad page."""

    def __init__(self, base: "Base"):
        self.base = base

    def state_dict(self) -> Dict[str, Any]:
        state_dict = self.base.state_dict()
        return state_dict

    def _get_default_device(self) -> str:
        output = subprocess.check_output(
            "ip route show default".split(), universal_newlines=True
        )
        words = output.split()
        device = None
        for cur, nex in zip(words, words[1:]):
            if cur == "dev":
                device = nex
        if not device:
            raise ValueError("No default device found")
        return device

    def _ip_of_device(self, device: str) -> str:
        output = subprocess.check_output(
            f"ip -4 a show dev {device}".split(), universal_newlines=True
        )
        ip = None
        for line in output.split("\n"):
            line = line.strip()
            if not line.startswith("inet"):
                continue
            ip = line.split()[1].split("/")[0]
            break
        if not ip:
            raise ValueError(f"ip not found for {device}")
        return ip

    def _qr_path(self, data) -> str:
        # from https://github.com/lincolnloop/python-qrcode/blob/master/qrcode/console_scripts.py
        module = "qrcode.image.svg.SvgPathImage"
        module, name = module.rsplit(".", 1)
        imp = __import__(module, {}, [], [name])
        SvgPathImage = getattr(imp, name)

        qr = qrcode.QRCode()
        qr.add_data(data)
        img = qr.make_image(image_factory=SvgPathImage)
        with io.BytesIO() as stream:
            img.save(stream)
            svg = stream.getvalue().decode()
        tag = svg.split("\n")[1]
        return tag

    def index(self, request: WSGIRequest) -> HttpResponse:
        """Renders the /network_info page. Only admin is allowed to see this page."""
        if not self.base.user_manager.is_admin(request.user):
            return redirect("login")
        context = self.base.context(request)

        ssid = None
        password = None
        try:
            ssid = subprocess.check_output(
                "/sbin/iwgetid --raw".split(), universal_newlines=True
            )[:-1]
            wifi_active = True
        except subprocess.CalledProcessError:
            wifi_active = False

        device = self._get_default_device()
        ip = self._ip_of_device(device)

        if wifi_active:
            try:
                password = subprocess.check_output(
                    ["sudo", "/usr/local/sbin/raveberry/password_for_ssid", ssid],
                    universal_newlines=True,
                )
            except subprocess.CalledProcessError:
                pass

        wifi_qr = self._qr_path(f"WIFI:S:{ssid};T:WPA;P:{password};;")
        raveberry_url = f"http://{ip}/"
        raveberry_qr = self._qr_path(raveberry_url)

        if wifi_active:
            context["ssid"] = ssid
            context["password"] = password
            context["wifi_qr"] = wifi_qr
        else:
            context["ssid"] = None
            context["password"] = None
            context["wifi_qr"] = None
        context["raveberry_url"] = raveberry_url
        context["raveberry_qr"] = raveberry_qr
        context["ip"] = ip
        return render(request, "network_info.html", context)
