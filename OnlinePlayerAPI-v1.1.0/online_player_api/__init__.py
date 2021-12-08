'''
Author       : noeru_desu
Date         : 2021-12-03 20:00:34
LastEditors  : noeru_desu
LastEditTime : 2021-12-03 20:41:20
Description  : 在线玩家API
'''

online_player = []
online_bot = []
all_online = []


def on_load(server, old):
    global online_player, online_bot, all_online
    try:
        online_player = old.online_player
        online_bot = old.online_bot
        all_online = old.all_online
    except Exception:
        pass


def on_server_stop(server, return_code):
    global online_player, online_bot, all_online
    online_player = []
    online_bot = []
    all_online = []


def on_player_joined(server, player, info):
    player_address = info.content.split('[')[1].split(']')[0]
    if player not in online_bot:
        if player_address == 'local':
            online_bot.append(player)
            all_online.append(player)
        else:
            online_player.append(player)
            all_online.append(player)
    else:
        server.logger.warning('玩家' + player + '的在线情况没有被记录')


def on_player_left(server, player):
    if player in online_player:
        online_player.remove(player)
        all_online.remove(player)
    elif player in online_bot:
        online_bot.remove(player)
        all_online.remove(player)


def check_online(player_name: str, player=True, bot=False) -> bool:
    if player and bot:
        return True if player_name in all_online else False
    elif player:
        return True if player_name in online_player else False
    elif bot:
        return True if player_name in online_bot else False


def get_player_list(player=True, bot=False) -> list[str]:
    if player and bot:
        return all_online
    elif player:
        return online_player
    elif bot:
        return online_bot


def have_player(player=True, bot=False) -> bool:
    if player and bot:
        return True if all_online else False
    elif player:
        return True if online_player else False
    elif bot:
        return True if online_bot else False
