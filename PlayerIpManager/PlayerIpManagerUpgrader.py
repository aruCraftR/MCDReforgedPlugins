# -*- coding: utf-8 -*-
from json import load as json_load
from os.path import join as path_join

from JsonDataAPI import Json

PLUGIN_METADATA = {
    'id': 'player_ip_manager_upgrader',
    'version': '1.0.0',
    'name': 'PlayerIpManagerUpgrader',
    'description': 'A Upgrader for PlayerIpManager 0.8.1 (upgrade to 0.8.2).',
    'author': 'noeru_desu',
    'link': 'https://github.com/noeru-desu/MCDReforgedPlugins/tree/main/PlayerIpManager',
    'dependencies': {
        'json_data_api': '*'
    }
}

server_path = './server'


def on_load(server, old):
    server.logger.info('[IpManager] 0.8.1->0.8.2升级器已加载')
    uuid = {}
    with open(path_join(server_path, 'usercache.json'), 'r') as f:
        user_cache = json_load(f)
    for i in user_cache:
        uuid[i['name']] = i['uuid']
    ip_library = Json('data', 'ip_library')
    ip_library_items = list(ip_library.items())
    for name, ips in ip_library_items:
        if name not in uuid:
            continue
        ip_library[uuid[name]] = ips
        del ip_library[name]
    ip_library.save()
    server.logger.info('[IpManager] 0.8.1->0.8.2升级器执行完毕')
    server.logger.info('[IpManager] 请使用!!ip reload ip命令重载ip库')
