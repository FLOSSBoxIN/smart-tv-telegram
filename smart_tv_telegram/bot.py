import typing

from pyrogram import Message, MessageHandler, Filters, ReplyKeyboardMarkup, KeyboardButton, Client, ReplyKeyboardRemove

from smart_tv_telegram import Config, Mtproto
from smart_tv_telegram.devices import UpnpDeviceFinder, ChromecastDeviceFinder
from smart_tv_telegram.devices.xbmc_device import XbmcDeviceFinder
from smart_tv_telegram.tools import named_media_types


_remove = ReplyKeyboardRemove()


class Bot:
    _config: Config
    _mtproto: Mtproto
    _states: typing.Dict[int, typing.Tuple[str, typing.Any]]

    def __init__(self, mtproto: Mtproto, config: Config):
        self._config = config
        self._mtproto = mtproto
        self._states = {}

    def _get_state(self, message: Message) -> typing.Tuple[typing.Union[bool, str], typing.Tuple[typing.Any]]:
        user_id = message.from_user.id

        if user_id in self._states:
            return self._states[user_id][0], self._states[user_id][1:]

        return False, tuple()

    def _set_state(self, message: Message, state: typing.Union[str, bool], *data: typing.Any):
        self._states[message.from_user.id] = (state, *data)

    def prepare(self):
        admin_filter = Filters.chat(self._config.admins)
        self._mtproto.register(MessageHandler(self._new_document, Filters.document & admin_filter))
        self._mtproto.register(MessageHandler(self._new_document, Filters.video & admin_filter))
        self._mtproto.register(MessageHandler(self._new_document, Filters.audio & admin_filter))
        self._mtproto.register(MessageHandler(self._new_document, Filters.animation & admin_filter))
        self._mtproto.register(MessageHandler(self._new_document, Filters.voice & admin_filter))
        self._mtproto.register(MessageHandler(self._new_document, Filters.video_note & admin_filter))
        self._mtproto.register(MessageHandler(self._play, Filters.text & admin_filter))

    # noinspection PyUnusedLocal
    async def _play(self, client: Client, message: Message):
        state, args = self._get_state(message)

        if state != "select":
            return

        self._set_state(message, False)

        if message.text == "Cancel":
            await message.reply("Cancelled", reply_markup=_remove)
            return

        # noinspection PyTupleAssignmentBalance
        msg_id, filename, devices = args

        try:
            device = next(
                device
                for device in devices
                if repr(device) == message.text
            )
        except StopIteration:
            await message.reply("Wrong device", reply_markup=_remove)
            return

        await device.stop()
        await device.play(f"http://{self._config.listen_host}:{self._config.listen_port}/stream/{msg_id}", filename)
        await message.reply(f"Playing ID: {msg_id}", reply_markup=_remove)

    # noinspection PyUnusedLocal
    async def _new_document(self, client: Client, message: Message):
        devices = []

        if self._config.upnp_enabled:
            devices.extend(await UpnpDeviceFinder.find(self._config))

        if self._config.chromecast_enabled:
            # noinspection PyUnresolvedReferences
            devices.extend(await ChromecastDeviceFinder.find(self._config))

        if self._config.xbmc_enabled:
            devices.extend(await XbmcDeviceFinder.find(self._config))

        if devices:
            file_name = ""

            for typ in named_media_types:
                obj = getattr(message, typ)

                if obj is not None:
                    file_name = obj.file_name
                    break

            self._set_state(message, "select", message.message_id, file_name, devices.copy())

            buttons = [[KeyboardButton(repr(device))] for device in devices]
            buttons.append([KeyboardButton("Cancel")])
            markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)

            await message.reply("Select a device", reply_markup=markup)

        else:
            await message.reply("Supported devices not found in the network", reply_markup=_remove)
