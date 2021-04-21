---
layout: default
nav_order: 3
---

# Configuration

All configuration is stored in the `config.yml` file.

Editing the configuration incorrectly can cause errors when you try to run the bot. Be carefull when editing the configuration.
{: .warn }

To edit the configuration, open `config.yml` and edit the options.

The configuration file should look something like this:

```yml
token: "TOKEN HERE"
database-uri: "postgres://highlight:PASSWORD HERE@localhost/highlight"
auto-update: true
```

Here is a table of valid configuration options:

| Option       | Description                                                                                                                                                                                 | Default  | Type    |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|---------|
| token        | The Discord API token for the bot. If you are unsure on how to create a bot and retrieve it's token see [this page](https://discordpy.readthedocs.io/en/latest/discord.html#discord-intro). | Required | String  |
| database-uri | The URI for the postgresql database.                                                                                                                                                        | Required | String  |
| auto-update  | Whether or not requied packages should be automaticly updated.                                                                                                                              | True     | Boolean |
