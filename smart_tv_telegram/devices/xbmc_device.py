# from: https://github.com/home-assistant/core/blob/dev/homeassistant/components/kodi/media_player.py

import asyncio
import json
import logging
import uuid
import aiohttp
import typing

from smart_tv_telegram import Config
from smart_tv_telegram.devices import Device, DeviceFinder


_LOGGER = logging.getLogger(__name__)

JSON_HEADERS = {"content-type": "application/json"}
JSONRPC_VERSION = "2.0"

ATTR_JSONRPC = "jsonrpc"
ATTR_METHOD = "method"
ATTR_PARAMS = "params"
ATTR_ID = "id"


class XbmcDeviceParams:
    _host: str
    _port: int
    _username: typing.Optional[str] = None
    _password: typing.Optional[str] = None

    def __init__(self, params: typing.Dict[str, typing.Any]):
        self._host = params["host"]
        self._port = params["port"]

        if "username" in params:
            self._username = params["username"]
            self._password = params["password"]

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def username(self) -> typing.Optional[str]:
        return self._username

    @property
    def password(self) -> typing.Optional[str]:
        return self._password


class XbmcDevice(Device):
    _auth: typing.Optional[aiohttp.BasicAuth]
    _http_url: str

    # noinspection PyMissingConstructor
    def __init__(self, device: XbmcDeviceParams):
        if device.username:
            self._auth = aiohttp.BasicAuth(device.username, device.password)
        else:
            self._auth = None

        self.device_name = "xbmc @{}".format(device.host)

        self._http_url = "http://{}:{}/jsonrpc".format(device.host, device.port)

    async def call(self, method, **args):
        data = {
            ATTR_JSONRPC: JSONRPC_VERSION,
            ATTR_METHOD: method,
            ATTR_ID: str(uuid.uuid4()),
            ATTR_PARAMS: args
        }

        response = None
        session = aiohttp.ClientSession(auth=self._auth, headers=JSON_HEADERS)

        try:
            response = await session.post(self._http_url, data=json.dumps(data))

            if response.status == 401:
                _LOGGER.error(
                    "Error fetching Kodi data. HTTP %d Unauthorized. "
                    "Password is incorrect.", response.status)
                return None

            if response.status != 200:
                _LOGGER.error(
                    "Error fetching Kodi data. HTTP %d", response.status)
                return None

            response_json = await response.json()
            print(response_json)

            if "error" in response_json:
                _LOGGER.error(
                    "RPC Error Code %d: %s",
                    response_json["error"]["code"],
                    response_json["error"]["message"])
                return None

            return response_json["result"]

        except (aiohttp.ClientError,
                asyncio.TimeoutError,
                ConnectionRefusedError):
            return None

        finally:
            if response:
                response.close()

            await session.close()

    async def stop(self):
        players = await self.call("Player.GetActivePlayers")

        if players:
            await self.call("Player.Stop", playerid=players[0]["playerid"])

    async def play(self, url: str, title: str):
        await self.call("Playlist.Clear", playlistid=0)
        await self.call("Playlist.Add", playlistid=0, item={"file": url})
        await self.call("Player.Open", item={"playlistid": 0}, options={"repeat": "one"})


class XbmcDeviceFinder(DeviceFinder):
    @staticmethod
    async def find(config: Config) -> typing.List[Device]:
        return [
            XbmcDevice(XbmcDeviceParams(params))
            for params in config.xbmc_devices
        ]
