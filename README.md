# real_time_vital


## quick start
```
pip install -r requirements.txt
bash real_time_vital.bash
```


### 实时生命体征数据获取
```
websocket_server
socket_server_manager
mqtt_client
socket_server
```

### 生命体征监测api
```
user_data_server
device_info_server
sms_verication_api
```


### 实时数据存储验证+实时数据存储线程
```
在socket_server_manager中实现该两个功能，使用线程池存储对应的实力
def create_sleep_storage_db_save():
    return SqlProvider(model=RealTimeVitalData, sql_config_path=SQL_CONFIG_PATH)


def create_sleep_storage():
    return SleepDataStorage(
        # sql_config_path=SQL_CONFIG_PATH,
        pool_size=10,
        max_normal_interval=60.0
    )

consumer_tool_pool.add_tool(
    tool_name="sleep_data_storage",
    tool_factory=create_sleep_storage,
    pool_size=3
)

consumer_tool_pool.add_tool(
    tool_name="sleep_data_storage_db_save",
    tool_factory=create_sleep_storage_db_save,
    pool_size=3
)
```

