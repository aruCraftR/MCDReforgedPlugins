# -*- coding: utf-8 -*-
from json import loads as json_loads, load as json_load
from re import search as re_search
from re import sub as re_sub
from urllib.request import Request, urlopen
from os.path import join as path_join

from ConfigAPI import Config
from geoip2.database import Reader as geoip2_Reader
from JsonDataAPI import Json
from mcdreforged.api.command import GreedyText, Literal, RequirementNotMet, Text, UnknownArgument
from mcdreforged.api.decorator import new_thread
from mcdreforged.api.types import ServerInterface

PLUGIN_METADATA = {
    'id': 'player_ip_manager',
    'version': '0.8.2',
    'name': 'PlayerIpManager',
    'description': 'Manage player IP',
    'author': 'noeru_desu',
    'link': 'https://github.com/noeru-desu/MCDReforgedPlugins/tree/main/PlayerIpManager',
    'dependencies': {
        'config_api': '*',
        'json_data_api': '*',
        'online_player_api': '*'
    }
}

server_path = './server'
Prefix = ['!!ip', '!!ip-segment']
online_player_ip = {}
uuid = {}
flipped_uuid = {}


class UUIDGetError(Exception):
    pass


def print_message(source, msg, tell=True, prefix='[IpManager] '):
    msg = prefix + str(msg)
    if source.is_player and not tell:
        source.get_server().say(msg)
    else:
        source.reply(msg)


def on_load(server: ServerInterface, old):
    global ip_library, GeoIP, config, online_player_ip
    OnlinePlayerAPI = server.get_plugin_instance('online_player_api')
    server.register_help_message('!!ip', '玩家ip库帮助')
    load_uuid()
    if old is not None:
        ip_library = old.ip_library
        GeoIP = old.GeoIP
        config = old.config
        online_player_ip = old.online_player_ip
    else:
        ip_library = Json('data', 'ip_library')
        config = Config('', default_config, 'PlayerIpManager')
        if (not config['disable-GeoIP']) or (not config['GeoIP-database-path'] == ''):
            GeoIP = geoip2_Reader(config['GeoIP-database-path'])
        else:
            GeoIP = 'disable'
        if '#banned-ip-segment' not in ip_library:
            ip_library['#banned-ip-segment'] = {}
            ip_library.save()
        online_player = OnlinePlayerAPI.get_player_list()
        for p in online_player:
            uuid = get_uuid(p)
            if uuid in ip_library:
                ip = ip_library[uuid][-1]
                if ip not in online_player_ip:
                    online_player_ip[ip] = []
                online_player_ip[ip].append(p)
    def_help_msg(', '.join(config['apis'].keys()))
    register_command(server)


def on_player_joined(server, player, info):
    global ip_library
    address = re_sub(r'[^a-z0-9\.]', '', re_search(r'\[.*:', info.content).group())
    if address == 'local':  # carpet假人地址为local
        return
    ip_segment = re_search(r'[1-9\.]+(?=\.)', address).group()
    if (config['single-ip-restrictions'] > 0) and (address not in config['ignore-single-ip-restrictions']) and (len(online_player_ip[address]) >= config['single-ip-restrictions']):
        server.execute(f'kick {player} 在你使用的IP地址上已有{len(online_player_ip[address])}名玩家在线')
    else:
        online_player_ip[address].append(player)
    if ip_segment in ip_library['#banned-ip-segment'].keys():
        server.execute('kick ' + player + ' ' + ip_library['#banned-ip-segment'][ip_segment])
    uuid = get_uuid(player)
    if uuid not in ip_library:
        ip_library[uuid] = []
    if address not in ip_library[uuid]:
        length = len(ip_library[uuid])
        if length >= config['maximum-ip-record']:
            if length == config['maximum-ip-record']:
                del ip_library[uuid][0]
            else:
                ip_library[uuid] = ip_library[uuid][int(-config['maximum-ip-record']):]
            ip_library.save()
        ip_library[uuid].append(address)
        ip_library.save()


def on_player_left(server, player):
    uuid = get_uuid(player)
    ip = ip_library[uuid][-1]
    if ip in online_player_ip:
        online_player_ip[ip].remove(player)


def load_uuid(check=None):
    global uuid, flipped_uuid
    with open(path_join(server_path, 'usercache.json'), 'r') as f:
        user_cache = json_load(f)
    for i in user_cache:
        uuid[i['name']] = i['uuid']
    flipped_uuid = {v: k for k, v in uuid.items()}
    if check is not None and check in uuid:
        return True
    else:
        return False


def get_uuid(player):
    if player not in uuid:
        if not load_uuid(player):
            raise UUIDGetError(f"Unable to get {player}'s uuid.")
    return uuid[player]


def reload_config():
    global config
    old_config = config
    try:
        config = Config('', default_config, 'PlayerIpManager')
        if config['disable-GeoIP'] != old_config['disable-GeoIP']:
            reload_db()
        if config['apis'] != old_config['apis']:
            def_help_msg(', '.join(config['apis'].keys()))
    except Exception as e:
        return '配置文件重载失败：' + e
    else:
        return '配置文件重载完成'


def reload_json():
    global ip_library
    try:
        ip_library = Json('data', 'ip_library')
    except Exception:
        return '玩家IP重载失败'
    else:
        return '玩家IP重载完成'


def reload_db():
    global GeoIP
    if config['disable-GeoIP']:
        return 'GeoIP查询未开启，取消重载'
    try:
        GeoIP = geoip2_Reader(config['GeoIP-database-path'])
    except Exception:
        return '数据库重载失败'
    else:
        return '数据库重载完成'


def get_ips(player):
    try:
        uuid = get_uuid(player)
    except UUIDGetError:
        return '玩家不存在'
    ip_num = len(ip_library[uuid])
    return '玩家{}使用过{}个ip登入服务器，具体如下(由旧到新)：{}'.format(player, ip_num, ', '.join(ip_library[uuid]))


def search_ip(ip):
    players = []
    for k, v in ip_library.items():
        if ip in v:
            players.append(flipped_uuid[k])
    if not players:
        return '没有查询到关联玩家'
    return '玩家{}使用过{}登入服务器'.format(', '.join(players), ip)


@new_thread(PLUGIN_METADATA['name'])
def search_geoip(source, ctx):
    if config['disable-GeoIP']:
        print_message(source, 'GeoIP查询未开启')
        return
    ctx = ctx_format(ctx)
    if len(ctx) == 1:
        print_message(source, ctx[0])
        return
    player, ip, num, reason = ctx
    if num == 'all':
        print_message(source, 'ip查询不支持使用参数all，自动选择为0')
    print_message(source, '正在搜索，请稍等')
    try:
        response = GeoIP.city(ip)
    except Exception as e:
        print_message(source, f'查找ip[{ip}]时出现错误，详细错误[{e}]')
        return
    print_message(source, f"""
    搜索完成，结果如下：
    时区：{response.location.time_zone}
    洲：{response.continent.names['zh-CN']}
    国：{response.country.names['zh-CN']}
    省：{response.subdivisions[0].names['zh-CN']}
    市：{response.city.names['zh-CN']}
    """)


@new_thread(PLUGIN_METADATA['name'])
def search_api(source, ctx):
    ctx = ctx_format(ctx, 0)
    if len(ctx) == 1:
        print_message(source, ctx[0])
        return
    player, ip, num, api_name = ctx
    if api_name not in config['apis'].keys():
        print_message(source, f'所指定的API[{api_name}]不存在')
        return
    api = config['apis'][api_name]
    url, header, status_name, status = None, None, None, None
    try:
        if 'url' not in api:
            print_message(source, f'所指定的API[{api_name}]的配置没有指定url')
            return
        else:
            url = api['url']
        if 'status' in api:
            status_name, status = api['status']
        if 'header' in api:
            header = api['header']
    except Exception as e:
        print_message(source, f'所指定的API[{api_name}]的配置出现错误：{e}')
        return
    url = re_sub(r'\[ip\]', ip, url)
    if num == 'all':
        print_message(source, 'ip查询不支持使用参数all，自动选择为0')
    print_message(source, '正在搜索，请稍等')
    try:
        request = Request(url)
        if header is not None:
            request.add_header(header[0], header[1])
        response = urlopen(request)
        content = response.read()
        encoding = response.info().get_content_charset('utf-8')
        data = json_loads(content.decode(encoding))
    except Exception as e:
        print_message(source, f'查询ip[{ip}]时出现错误，详细错误[{e}]')
        return
    if status_name is not None:
        if data[status_name] != status:
            print_message(source, 'API响应：获取失败')
            return
    text_list = []
    try:
        for i, j in api['response']:
            text_list.append(i + data[j])
    except Exception as e:
        print_message(source, f'读取响应信息时出现错误，详细错误[{e}]')
        print_message(source, f'响应信息：[{data}]')
        return
    print_message(source, """
    搜索完成，结果如下：
    {}
    """.format('\n'.join(text_list)))


def execute_cmd(server, cmd, ip, reason=None):
    cmd = cmd + ' ' + ip
    if reason is not None:
        cmd = cmd + ' ' + reason
    server.execute(cmd)


def ban_ip(server, ctx):
    ctx = ctx_format(ctx)
    if len(ctx) == 1:
        return ctx[0]
    player, ip, num, reason = ctx
    cmd = 'ban-ip'
    if not num == 'all':
        execute_cmd(server, cmd, ip, reason)
        return '已完成操作'
    for i in ip_library[get_uuid(player)]:
        execute_cmd(server, cmd, i, reason)
    return '已完成操作'


def unban_ip(server, ctx):
    ctx = ctx_format(ctx)
    if len(ctx) == 1:
        return ctx[0]
    player, ip, num, reason = ctx
    cmd = 'pardon-ip'
    if not num == 'all':
        execute_cmd(server, cmd, ip, reason)
        return '已完成操作'
    for i in ip_library[get_uuid(player)]:
        execute_cmd(server, cmd, i, reason)
    return '已完成操作'


def ban_ip_segment(server, ctx):
    ctx = ctx_format(ctx)
    if len(ctx) == 1:
        return ctx[0]
    player, ip, num, reason = ctx
    if reason is None:
        reason = 'Banned by an operator'
    server.execute('kick ' + player + ' ' + reason)
    if not num == 'all':
        ip_segment = re_search(r'[1-9\.]+(?=\.)', ip).group()
        ip_library['#banned-ip-segment'][ip_segment] = reason
        ip_library.save()
        return '已完成操作'
    for i in ip_library[get_uuid(player)]:
        ip_segment = re_search(r'[1-9\.]+(?=\.)', i).group()
        if ip_segment not in ip_library['#banned-ip-segment']:
            ip_library['#banned-ip-segment'][ip_segment] = reason
    ip_library.save()
    return '已完成操作'


def unban_ip_segment(server, ctx):
    ctx = ctx_format(ctx)
    if len(ctx) == 1:
        return ctx[0]
    player, ip, num, reason = ctx
    if not num == 'all':
        ip_segment = re_search(r'[1-9\.]+(?=\.)', ip).group()
        del ip_library['#banned-ip-segment'][ip_segment]
        ip_library.save()
        return '已完成操作'
    for i in ip_library[get_uuid(player)]:
        ip_segment = re_search(r'[1-9\.]+(?=\.)', i).group()
        del ip_library['#banned-ip-segment'][ip_segment]
        ip_library.save()
    return '已完成操作'


def ctx_format(ctx, del_num: int = None):
    if del_num is not None:
        ctx = ctx.split(' ', 3)
        reason = ctx[del_num]
        del ctx[del_num]
    else:
        ctx = ctx.split(' ', 2)
        reason = None
    length = len(ctx)
    player = ctx[0]
    try:
        uuid = get_uuid(player)
    except UUIDGetError:
        return ('玩家不存在',)
    if length == 1:
        ctx.append(0)
    try:
        num = int(ctx[1]) - 1
    except Exception:
        if ctx[1] == 'all':
            num = 'all'
        else:
            return ('参数错误，序号不为纯数字或all',)
    else:
        try:
            if not num == 'all':
                ip = ip_library[uuid][num]
            else:
                ip = ip_library[uuid][-1]
        except IndexError:
            return ('序号错误，给出的序号不存在',)
    if length == 3:
        reason = ctx[2]
    return (player, ip, num, reason)


def register_command(server):
    server.register_command(
        Literal(Prefix[0]).
        requires(lambda src: src.has_permission(config['permission-requirement'])).
        on_error(RequirementNotMet, lambda src: print_message(src, '§4权限不足！'), handled=True).
        on_error(UnknownArgument, lambda src: print_message(src, f'§c未知指令，输入§7{Prefix[0]}§c以查看帮助')).
        runs(lambda src: print_message(src, help_msg)).
        then(
            Literal('reload').
            then(Literal('config').runs(lambda src: print_message(src, reload_config()))).
            then(Literal('ip').runs(lambda src: print_message(src, reload_json()))).
            then(Literal('geoip').runs(lambda src: print_message(src, reload_db())))
        ).
        then(Literal('get').then(Text('player').runs(lambda src, ctx: print_message(src, get_ips(ctx['player']))))).
        then(Literal('search').then(Text('player').runs(lambda src, ctx: print_message(src, search_ip(ctx['player']))))).
        then(Literal('geoip').then(GreedyText('parameter').runs(lambda src, ctx: search_geoip(src, ctx['parameter'])))).
        then(Literal('api').then(GreedyText('parameter').runs(lambda src, ctx: search_api(src, ctx['parameter'])))).
        then(Literal('ban').then(GreedyText('parameter').runs(lambda src, ctx: print_message(src, ban_ip(src.get_server(), ctx['parameter']))))).
        then(Literal('unban').then(GreedyText('parameter').runs(lambda src, ctx: print_message(src, unban_ip(src.get_server(), ctx['parameter'])))))
    )
    server.register_command(
        Literal(Prefix[1]).
        requires(lambda src: src.has_permission(config['permission-requirement'])).
        on_error(RequirementNotMet, lambda src: print_message(src, '§4权限不足！'), handled=True).
        on_error(UnknownArgument, lambda src: print_message(src, f'§c未知指令，输入§7{Prefix[0]}§c以查看帮助')).
        runs(lambda src: print_message(src, help_msg)).
        then(
            Literal('ban').
            runs(lambda src: print_message(src, help_msg)).
            then(GreedyText('parameter').runs(lambda src, ctx: print_message(src, ban_ip_segment(src.get_server(), ctx['parameter']))))
        ).
        then(
            Literal('unban').
            runs(lambda src: print_message(src, help_msg)).
            then(GreedyText('parameter').runs(lambda src, ctx: print_message(src, unban_ip_segment(src.get_server(), ctx['parameter']))))
        )
    )


def def_help_msg(apis):
    global help_msg
    help_msg = """
------ {1} v{2} ------
根据玩家加入时的ip识别来记录ip
[必填]  <可选>  “|”表示“或”
§7{0}§r 显示帮助信息
§7{0} reload [config|ip|geoip]§r 重载信息
§7{0} get [player]§r 获取指定玩家ip列表
§7{0} search [ip]§r 查询指定ip所记录的玩家
§7{0} geoip [player] <number>§r 在GeoLite2-City数据库中查找指定玩家的ip归属地
§7{0} api [api-name] [player] <number>§r 在指定API上查找指定玩家的ip归属地(在线查询)
§7已从配置文件中加载的API：{4}§r
§7{0} ban [player] <number> <reason>§r 封锁掉指定玩家的ip
§7{0} unban [player] <number>§r 解封掉指定玩家的ip
§7{3} ban [player] <number> <reason> 封锁掉指定玩家的ip段
§7{3} unban <number> [player]§r 解封掉指定玩家的ip段
参数说明：ip段使用/24  [player]为玩家名  <number>为ip序号，默认0(最新)，可使用all来指定列表中的所有ip  <reason>为封禁理由
""".format(Prefix[0], PLUGIN_METADATA['name'], PLUGIN_METADATA['version'], Prefix[1], apis)


default_config = {
    'permission-requirement': 3,
    'maximum-ip-record': 10,
    'single-ip-restrictions': 1,
    'ignore-single-ip-restrictions': [
        '127.0.0.1'
    ],
    'disable-GeoIP': False,
    'GeoIP-database-path': '',
    'apis': {
        'ip-api': {
            'url': 'http://ip-api.com/json/[ip]?lang=zh-CN',
            'status': ['status', 'success'],
            'response': [
                ['时区：', 'timezone'],
                ['国家：', 'country'],
                ['省：', 'regionName'],
                ['市：', 'city'],
                ['ISP：', 'isp']
            ]
        }
    }
}
