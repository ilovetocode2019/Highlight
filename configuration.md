---
layout: default
nav_order: 3
---

# Configuration

All configuration is stored in the `config.py` file. Each configuration value is stored as a variable in the config file.

Editing the configuration incorrectly could cause the bot to crash on startup
{: .warn }

To edit the configuration, open the file and change the values. The `config.py` file will look something like this:

```python
token = "TOKEN HERE"
database_uri = "postgres://highlight:PASSWORD HERE@localhost/highlight"
console = 12345678912345678
```

Here is the format for the file:

```python
option = "text value (quoted)"
option = 12345678912345678
```

Here is a table of configuration options:

| Option       | Description                                                                                                                                                                                               | Default  | Type    |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|---------|
| token        | The Discord API token for the bot. If your unsure how to get a token see [this page](https://discordpy.readthedocs.io/en/latest/discord.html#discord-intro).                                                            | Required | String  |
| database_uri | The URI for the postgresql. database                                                                                                                                                                      | Required | String  |
| console      | The channel ID to log information to. To copy a channel ID go to `Settings > Advanced` and then select Developer mode. An option for copying the channel ID will appear, when right clicking any channel. | Required | Integer |
