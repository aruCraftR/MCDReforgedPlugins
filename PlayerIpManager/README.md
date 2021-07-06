### 注意：此插件仅能在服务器使用公网IP或proxy protocol的情况下才可记录玩家IP（即服务端可获取到玩家真实IP）。暂时只支持vanilla_handler（Vanilla / Carpet / Fabric server）

## 依赖

### Python包

- `geoip2` `urllib`

### MCDReforged
- 版本>=1.0.0

### 前置插件

- [ConfigAPI](https://github.com/hanbings/ConfigAPI)
- [JsonDataAPI](https://github.com/zhang-anzhi/MCDReforgedPlugins/tree/master/JsonDataAPI)

## 配置

配置文件位于 `config\PlayerIpManager.yml`

默认配置：
```
apis:
  ip-api:
    response:
    - [时区：, timezone]
    - [国家：, country]
    - [省：, regionName]
    - [市：, city]
    - [ISP：, isp]
    status: [status, success]
    url: http://ip-api.com/json/[ip]?lang=zh-CN
permission-requirement: 3
maximum-ip-record: 10
single-ip-restrictions: 1
ignore-single-ip-restrictions:
  - 127.0.0.1
disable-GeoIP: false
GeoIP-database-path: ''
```
### `permission-requirement`

默认值: `3`

用于设置`!!ip`命令所需的权限等级

### `maximum-ip-record`

默认值: `10`

用于设置对于每个玩家记录的最多IP数量

超过限制后最新的IP会替换掉最旧的IP

对于国内的互联网服务提供商(ISP)，每次重新进行拨号(可以理解成重启光猫/路由器)都会导致IP变动

### `single-ip-restrictions`

默认值: `1`

用于设置对于每个连接的ip最多能有多少玩家在线

如果有超过该值数量的玩家使用同一ip登入，将会自动踢出

典型用途：自动踢出玩家小号

### `ignore-single-ip-restrictions`

默认值: `127.0.0.1`

在该列表中的ip将不会检测执行自动踢出操作

典型用途：使用内网映射导致所有玩家ip均为127.0.0.1，会无差别踢出超过设置数量的玩家

### `disable-GeoIP`

默认值: `false`

开启或关闭GeoIP数据库查询功能

### `GeoIP-database-path`

默认值: `无`

用于设置GeoIP数据库文件路径，请使用后缀为`.mmdb`的文件

请自行在网上搜索GeoIP数据库的获取方法(GeoIP有免费数据库：GeoLite2。建议使用city版本)

如果不想费时间去找，可将`disable-GeoIP`选项设置为`true`来关闭GeoIP查询功能

### `apis`

默认值: 
```
ip-api:
  response:
  - [时区：, timezone]
  - [国家：, country]
  - [省：, regionName]
  - [市：, city]
  - [ISP：, isp]
  status: [status, success]
  url: http://ip-api.com/json/[ip]?lang=zh-CN
```

用于设置自定义在线IP查询接口(默认的可直接使用)

可以设置多个接口，接口的响应信息必须是json文本，仅支持GET方法，可使用附加header进行身份验证

具体格式如下：

```
<api显示名称>:
  response:
  - [<内容解释>, <响应内的键>]
  - [<内容解释>, <响应内的键>]
  - ...
  status: [<响应内表示状态信息的键>, <键内表示成功状态的值>]
  url: <请求地址>(请使用[ip]替换掉请求时需要发送的ip地址)
<api2显示名称>:
  response:
  - [<内容解释>, <响应内的键>]
  - [<内容解释>, <响应内的键>]
  - ...
  url: <请求地址>(请使用[ip]替换掉请求时需要发送的ip地址)
  header: [<header名称>, <header内容>]
<api3显示名称>:
...
```

其中`header`和`status`为可选项，在需要时添加即可

实在不知道apis配置是如何与响应信息对应的，可以参照ip-api的配置与响应进行了解

## 命令

控制台或游戏内输入`!!ip`即可查看帮助
