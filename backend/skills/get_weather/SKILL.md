---
name: 天气查询
description: 查询指定城市的实时天气信息和未来预报
---

# 天气查询技能

这个技能用于查询指定城市的天气信息，包括实时天气和未来7天预报。

## 使用步骤

1. 根据城市名获取对应的经纬度坐标
2. 调用 open-meteo.com API 获取天气数据
3. 解析并整理天气信息
4. 以友好的格式回复用户

## 具体操作

### 步骤1：城市坐标查询

使用地理编码 API 获取城市的经纬度：

```
fetch_url(url="https://geocoding-api.open-meteo.com/v1/search?name={城市名}&count=1&language=zh&format=json")
```

**常用城市坐标**（可预先记忆）：
- 北京：latitude=39.9042, longitude=116.4074
- 上海：latitude=31.2304, longitude=121.4737
- 广州：latitude=23.1291, longitude=113.2644
- 深圳：latitude=22.5431, longitude=114.0579
- 杭州：latitude=30.2741, longitude=120.1551
- 成都：latitude=30.5728, longitude=104.0668

### 步骤2：获取天气数据

调用 open-meteo 天气 API：

```
fetch_url(url="https://api.open-meteo.com/v1/forecast?latitude={纬度}&longitude={经度}&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=Asia/Shanghai")
```

**API 参数说明**：
- `latitude`：纬度
- `longitude`：经度
- `daily`：每日预报字段
  - `weather_code`：天气代码
  - `temperature_2m_max`：最高温度
  - `temperature_2m_min`：最低温度
- `timezone`：时区（Asia/Shanghai）

### 步骤3：天气代码对照

将天气代码转换为中文描述：

| 代码 | 天气 |
|------|------|
| 0 | ☀️ 晴 |
| 1, 2, 3 | ⛅ 多云 |
| 45, 48 | 🌫️ 雾 |
| 51, 53, 55 | 🌧️ 毛毛雨 |
| 61, 63, 65 | 🌧️ 雨 |
| 71, 73, 75 | ❄️ 雪 |
| 80, 81, 82 | 🌧️ 阵雨 |
| 95, 96, 99 | ⛈️ 雷暴 |

## 输出格式

请将获取到的天气信息整理成以下格式回复用户：

```
【{城市名}未来七天天气预报】（{日期范围}）

| 日期 | 天气 | 最高温 | 最低温 |
|------|------|--------|--------|
| 月日 | ⛅ 天气 | 温度°C | 温度°C |
| ... | ... | ... | ... |

### 📌 温馨提示
- 根据天气情况给出适当建议
- 提醒用户注意防晒/防雨/防寒等
```

## 完整查询示例

查询北京天气（使用已知坐标）：

1. 直接使用已知坐标调用 API：
```
fetch_url(url="https://api.open-meteo.com/v1/forecast?latitude=39.9042&longitude=116.4074&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=Asia/Shanghai")
```

2. 解析返回的 JSON 数据，提取：
   - `daily.time`：日期列表
   - `daily.weather_code`：天气代码列表
   - `daily.temperature_2m_max`：最高温列表
   - `daily.temperature_2m_min`：最低温列表

3. 将天气代码转换为中文，整理成表格输出

## 注意事项

- 优先使用已知城市坐标以提高查询速度
- 如果城市不在已知列表中，先调用 geocoding API 获取坐标
- API 返回的是未来7天的数据
- 如果 API 调用失败，友好提示用户稍后重试
