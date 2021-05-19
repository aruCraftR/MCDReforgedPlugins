### 注意：此插件仅能在服务器使用公网IP或proxy protocol的情况下才可记录玩家IP（即服务端可获取到玩家真实IP）。暂时只支持vanilla_handler（Vanilla / Carpet / Fabric server）

## 依赖

### Python包

- `geoip2`

### MCDReforged
- 版本高于1.0.0

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
    url: http://ip-api.com/json/[ip]?lang=zh-CN
permission-requirement: 3
maximum-ip-record: 10
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
  url: http://ip-api.com/json/[ip]?lang=zh-CN
```

用于设置自定义在线IP查询接口

可以设置多个接口，接口的响应信息必须是json文本，仅支持GET方法，可使用附加header进行身份验证

具体格式如下：

```
<api显示名称>:
  response:
  - [<内容解释>, <响应信息内的key>]
  - [<内容解释>, <响应信息内的key>]
  - ...
  url: <请求地址>(请使用[ip]替换掉请求时需要发送的ip地址)
<api2显示名称>:
  response:
  - [<内容解释>, <响应信息内的key>]
  - [<内容解释>, <响应信息内的key>]
  - ...
  url: <请求地址>(请使用[ip]替换掉请求时需要发送的ip地址)
  header: [<header名称>, <header内容>]
<api3显示名称>:
...
```

其中`header`为可选项，在需要时添加即可

## 命令

控制台或游戏内输入`!!ip`即可查看帮助
