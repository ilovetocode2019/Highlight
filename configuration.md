# Configuration

All configuration is stored in the `config.py` file. Each configuration value is stored as a variable in the config file.

To edit the configuration, open the file and change the values. The `config.py` file will look something like this:

```python
option = "text value (quoted)"
option = 12345678912345678
```

Here is a table of configuration options:

| Option       | Description |
|--------------|-------------|
| token        | The Discord API token for the bot. If your unsure how to get a token see https://discordpy.readthedocs.io/en/latest/discord.html#discord-intro |
| database_uri | The URI for the postgresql database |
| console      | The channel ID to log information to. To copy a channel ID go to `Settings > Advanced` and then select Developer mode. An option for copying the channel ID will appear, when right clicking any channel. |
