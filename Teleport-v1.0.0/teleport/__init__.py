'''
Author       : noeru_desu
Date         : 2021-12-03 06:31:49
LastEditors  : noeru_desu
LastEditTime : 2021-12-05 15:08:30
Description  : 传送相关命令
'''
from os import makedirs
from os.path import join, exists, isfile
from json import load, dump
from re import match, search

from teleport.dimension import get_dimension
from teleport.position import Position
from mcdreforged.api.all import *


class Json(dict):
    def __init__(self, file: str, folder: str = None, default_json: dict = None, separators=(', ', ': ')):
        self.separators = separators
        if folder is None:
            self.path = file
        else:
            if not exists(folder):
                makedirs(folder)
            self.path = join(folder, file)
        if isfile(self.path):
            with open(self.path, encoding='utf-8') as f:
                super().__init__(load(f))
        else:
            super().__init__()
            if default_json is not None:
                self.update(default_json)
            self.save()

    def save(self, replaced_dict: dict = None, use_indent: bool = True):
        if replaced_dict is not None:
            self.clear()
            self.update(replaced_dict)
        with open(self.path, 'w', encoding='utf-8') as f:
            if use_indent:
                dump(self.copy(), f, indent=4, ensure_ascii=False)
            else:
                dump(self.copy(), f, separators=self.separators, ensure_ascii=False)


class TpaRequest(object):
    def __init__(self, source: PlayerCommandSource, target_player: str, pull: bool):
        self.source_player = source.player
        if OnlinePlayerAPI.check_online(target_player, False, True):
            source.reply("§b对方为bot，正在传送")
            if pull:
                server_inst.execute(f'tp {target_player} {self.source_player}')
            else:
                register_back_pos(self.source_player)
                server_inst.execute(f'tp {self.source_player} {target_player}')
            return
        self.source = source
        self.pull = pull
        self.target_player = target_player
        error = check_request(self.source_player, target_player)
        if error is not None:
            source.reply(error)
            return
        request_dict[self.source_player] = requested_dict[target_player] = self
        source.reply(RTextList(
            RText('§b传送请求已发送至玩家 §e{}  '.format(target_player)),
            RText('[取消传送请求]', color=RColor.gold).h('§b点击取消传送请求').c(RAction.run_command, '!!tpcancel')
        ))
        server_inst.execute(f'execute at {target_player} run playsound minecraft:entity.experience_orb.pickup player {target_player} ~ ~ ~ 2 0.5')
        server_inst.tell(target_player, RTextList(
            RText(f'§b玩家 §e{self.source_player} §b想传送到你身边'),
            RText('  '),
            RText('[同意]', color=RColor.green).h('§b点击同意传送请求').c(RAction.run_command, '!!tpaccept'),
            RText('  '),
            RText('[拒绝]', color=RColor.red).h('§b点击拒绝传送请求').c(RAction.run_command, '!!tpdeny')
        ))

    def accept(self, source: PlayerCommandSource):
        if self.pull:
            register_back_pos(self.target_player)
            server_inst.execute(f'tp {self.target_player} {self.source_player}')
        else:
            register_back_pos(self.source_player)
            server_inst.execute(f'tp {self.source_player} {self.target_player}')
        self.source.reply("§b对方已接受传送请求，正在传送")
        source.reply("§b正在传送")
        self.delet()

    def cancel(self, source: PlayerCommandSource):
        source.reply(f"§b发送给{self.target_player}的传送请求已取消")
        server_inst.tell(self.target_player, f"§b{self.source_player}已取消传送请求")
        self.delet()

    def deny(self, source: PlayerCommandSource):
        source.reply(f"§b发送给{self.target_player}的传送请求已取消")
        self.source.reply(f"§b{self.source_player}已取消传送请求")
        self.delet()

    def delet(self):
        del request_dict[self.source_player]
        del requested_dict[self.target_player]


OnlinePlayerAPI = ...
home_pos_dict: Json
back_pos_dict: Json
requested_dict = {}
request_dict = {}
prefixes = ('!!tpa', '!!tpahere', '!!tpaccept', '!!tpcancel', '!!tpdeny', '!!sethome', '!!home', '!!back')
server_inst: PluginServerInterface
home_pos_file_path = join('config', 'teleport_data')
back_pos_file_path = join('config', 'teleport_data')


def process_coordinate(text: str) -> Position:
    data = text[1:-1].replace('d', '').split(', ')
    data = [(x + 'E0').split('E') for x in data]
    assert len(data) == 3
    return Position(*[float(e[0]) * 10 ** int(e[1]) for e in data])


def process_dimension(text: str) -> str:
    return text.replace(match(r'[\w ]+: ', text).group(), '', 1).strip('"\' ')


def check_request(source_player, target_player):
    if not OnlinePlayerAPI.check_online(target_player, True, True):
        return "§c玩家不在线"
    elif target_player == source_player:
        return "§c请不要原地TP"
    elif source_player in request_dict:
        return f"§c你已有一个请求发送给§e{request_dict[source_player].target_player}"
    elif target_player in requested_dict:
        return f"§c请稍等, 对方正在处理§e{requested_dict[target_player].target_player}§c的传送请求"


def tpa_command(source: CommandSource, target_player):
    if source.is_console:
        return
    TpaRequest(source, target_player, False)


def tpahere_command(source: CommandSource, target_player):
    if source.is_console:
        return
    TpaRequest(source, target_player, True)


def tpaccept_command(source: CommandSource):
    if source.is_console:
        return
    player = source.player
    if player not in requested_dict:
        source.reply('§c你没有收到待处理的传送请求')
        return
    requested_dict[player].accept(source)


def tpcancel_command(source: CommandSource):
    if source.is_console:
        return
    player = source.player
    if player not in request_dict:
        source.reply('§c你没有发出待处理的传送请求')
        return
    request_dict[player].cancel(source)


def tpdeny_command(source: CommandSource):
    if source.is_console:
        return
    player = source.player
    if player not in requested_dict:
        source.reply('§c你没有收到待处理的传送请求')
        return
    requested_dict[player].deny(source)


def get_player_pos(player):
    position = process_coordinate(search(r'\[.*]', server_inst.rcon_query(f'data get entity {player} Pos')).group())
    dimension = process_dimension(server_inst.rcon_query(f'data get entity {player} Dimension'))
    return position, get_dimension(dimension)


def sethome_command(source: CommandSource):
    if source.is_console:
        return
    if server_inst.is_rcon_running():
        player = source.player
        position, dimension = get_player_pos(player)
        home_pos_dict[player] = [dimension.get_reg_key(), round(position.x, 2), round(position.y, 2), round(position.z, 2)]
        source.reply(RTextList('设定家至', dimension.get_rtext(), ' ', int(position.x), ' ', int(position.y), ' ', int(position.z)))
        home_pos_dict.save(use_indent=False)


def home_command(source: CommandSource):
    if source.is_console:
        return
    player = source.player
    if player not in home_pos_dict:
        source.reply(f"§c请先使用 §6{prefixes[5]}§c 设置家！")
        return
    data = home_pos_dict[player]
    register_back_pos(player)
    server_inst.execute(f'execute in {data[0]} run teleport {player} {data[1]} {data[2]} {data[3]}')


def back_command(source: CommandSource):
    if source.is_console:
        return
    player = source.player
    data = back_pos_dict[player]
    register_back_pos(player)
    server_inst.execute(f'execute in {data[0]} run teleport {player} {data[1]} {data[2]} {data[3]}')


def register_back_pos(player):
    if server_inst.is_rcon_running():
        position, dimension = get_player_pos(player)
        back_pos_dict[player] = [dimension.get_reg_key(), round(position.x, 2), round(position.y, 2), round(position.z, 2)]


def on_player_left(server: PluginServerInterface, player):
    if player in requested_dict:
        tpa_request: TpaRequest = requested_dict[player]
        server.tell(tpa_request.source_player, f"§b玩家 §e{player} §b已退出, 传送请求自动取消")
        tpa_request.delet()
    elif player in request_dict:
        tpa_request: TpaRequest = request_dict[player]
        server.tell(tpa_request.target_player, f"§b玩家 §e{player} §b已退出, 传送请求自动取消")
        tpa_request.delet()


def on_load(server: PluginServerInterface, old):
    global server_inst, OnlinePlayerAPI, home_pos_dict, back_pos_dict, request_dict, requested_dict
    server_inst = server
    OnlinePlayerAPI = server.get_plugin_instance('online_player_api')
    server.register_help_message(prefixes[0], '申请传送至其他玩家')
    server.register_help_message(prefixes[1], '申请其他玩家传送至你')
    server.register_help_message(prefixes[5], '设置家')
    server.register_help_message(prefixes[6], '返回家')
    server.register_help_message(prefixes[7], '返回最近一次传送前的位置')
    server.register_command(
        Literal(prefixes[0]).then(Text('player').runs(lambda src, ctx: tpa_command(src, ctx['player'])))
    )
    server.register_command(
        Literal(prefixes[1]).then(Text('player').runs(lambda src, ctx: tpahere_command(src, ctx['player'])))
    )
    server.register_command(
        Literal(prefixes[2]).runs(lambda src: tpaccept_command(src))
    )
    server.register_command(
        Literal(prefixes[3]).runs(lambda src: tpcancel_command(src))
    )
    server.register_command(
        Literal(prefixes[4]).runs(lambda src: tpdeny_command(src))
    )
    server.register_command(
        Literal(prefixes[5]).runs(lambda src: sethome_command(src))
    )
    server.register_command(
        Literal(prefixes[6]).runs(lambda src: home_command(src))
    )
    server.register_command(
        Literal(prefixes[7]).runs(lambda src: back_command(src))
    )
    try:
        home_pos_dict = old.home_pos_dict
        back_pos_dict = old.back_pos_dict
        request_dict = old.request_dict
        requested_dict = old.requested_dict
    except Exception:
        home_pos_dict = Json('home.json', home_pos_file_path, separators=(',', ':'))
        back_pos_dict = Json('back.json', back_pos_file_path, separators=(',', ':'))


def on_unload(server: PluginServerInterface):
    back_pos_dict.save(use_indent=False)
