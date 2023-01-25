import asyncio
import json
import os

from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus, MessagesFilter, ParseMode
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from config import api_id, api_hash, proxy, admin_id, send_message_link


# Init groups config
if not os.path.isfile('groups.json'):
    with open('groups.json', 'w') as f:
        json.dump({}, f)

with open('groups.json', 'r', encoding='utf-8') as f:
    groups: dict[str, int] = json.load(f)


bot = Client('bot', api_id=api_id, api_hash=api_hash, proxy=proxy)
handler: MessageHandler


@bot.on_message(filters.command('help') & filters.private)
async def help_info(c: Client, m: Message):
    await m.reply('''
/set_channel <channel_id> - 设置目标频道
/unset_channel - 取消设置目标频道
/init_channel - 初始化目标频道（转发现有的置顶消息到目标频道）
'''.strip(), parse_mode=ParseMode.MARKDOWN)


@bot.on_message(filters.command('set_channel') & filters.group & filters.user(admin_id))
async def set_group_channel(c: Client, m: Message):
    global handler
    # Check if message sender is admin or creator
    sender = await c.get_chat_member(m.chat.id, m.from_user.id)
    if sender.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        await m.reply_text('只有群组的管理员才能设置目标频道。')
        return

    # Get channel id and check if bot is admin there
    channel_id = m.text.split(' ', 1)[1]
    try:
        channel_id = int(channel_id)
    except ValueError:
        await m.reply_text('频道 ID 有误。')
        return
    bot_in_channel = await c.get_chat_member(channel_id, 'me')
    if bot_in_channel.status != ChatMemberStatus.ADMINISTRATOR or \
            bot_in_channel.privileges.can_post_messages is False:
        await m.reply_text('请先将机器人添加为此频道管理员，并给予发送消息的权限。')
        return

    groups[str(m.chat.id)] = channel_id

    # Save
    with open('groups.json', 'w', encoding='utf-8') as f:
        json.dump(groups, f, indent=4)
    bot.remove_handler(handler)
    handler = MessageHandler(monitor_new_pinned_message,
                             filters.chat([int(i) for i in groups.keys()]) & filters.pinned_message)
    bot.add_handler(handler)

    await m.reply_text('设置成功。')


@bot.on_message(filters.command('unset_channel') & filters.group & filters.user(admin_id))
async def unset_group_channel(c: Client, m: Message):
    global handler
    # Check if message sender is admin or creator
    sender = await c.get_chat_member(m.chat.id, m.from_user.id)
    if sender.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        await m.reply_text('只有群组的管理员才能取消目标频道。')
        return

    groups.pop(str(m.chat.id), None)

    # Save
    with open('groups.json', 'w', encoding='utf-8') as f:
        json.dump(groups, f, indent=4)
    bot.remove_handler(handler)
    handler = MessageHandler(monitor_new_pinned_message,
                             filters.chat([int(i) for i in groups.keys()]) & filters.pinned_message)
    bot.add_handler(handler)

    await m.reply_text('取消成功。')


@bot.on_message(filters.command('init_channel') & filters.group & filters.user(admin_id))
async def initialize_group_channel(c: Client, m: Message):
    # Check if message sender is admin or creator
    sender = await c.get_chat_member(m.chat.id, m.from_user.id)
    if sender.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        await m.reply_text('只有群组的管理员才能设置目标频道。')
        return

    if str(m.chat.id) not in groups:
        await m.reply_text('请先使用 /set_channel 设置目标频道。')
        return

    messages = []
    async for message in c.search_messages(m.chat.id, filter=MessagesFilter.PINNED):
        messages.append(message.id)
    messages.sort()

    channel_id = groups[str(m.chat.id)]
    channel_id_tapi = str(channel_id).removeprefix('-100')
    for message_id in messages:
        if send_message_link:
            await c.send_message(channel_id, 'https://t.me/c/{}/{}'.format(channel_id_tapi, message_id))
        await bot.forward_messages(channel_id, m.chat.id, message_id, True)

    await m.reply_text('已将置顶消息全部转发到目标频道。')
    del messages


async def monitor_new_pinned_message(c: Client, m: Message):
    if str(m.chat.id) not in groups:
        return
    channel_id = groups[str(m.chat.id)]
    chat_id_tapi = str(m.chat.id).removeprefix('-100')
    if send_message_link:
        await c.send_message(channel_id, 'https://t.me/c/{}/{}'.format(chat_id_tapi, m.pinned_message.id))
    await m.pinned_message.forward(channel_id, True)


async def main():
    global handler, groups
    handler = MessageHandler(monitor_new_pinned_message,
                             filters.chat([int(i) for i in groups.keys()]) & filters.pinned_message)
    handler, _ = bot.add_handler(handler)
    await bot.start()
    await idle()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
