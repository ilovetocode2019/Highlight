# Highlight

A Discord bot that notifies you through DMs when a highlight word is found in a channel.

If you have questions or issues, feel free to join the [support server](https://discord.gg/eHxvStNJb7) on Discord.

## Features
- DM notifications for highlight words
- Time zone configuration
- Temporarily disable Highlight
- Block users or channel
- Import lists from other servers

## Installation

1. **Download the bot as a Git repository**

If you don't have Git installed you can [download it here](https://git-scm.com/downloads).

Once you install Git, you can clone the bot in the terminal/command line using `git clone https://github.com/ilovetocode2019/Highlight.git`

2. **Download Python**

You can [download Python here](https://www.python.org/downloads/). You will need to use python 3.7+.

3. **Install required dependencies**

On windows you should run `python -m pip install -r requirements.txt` in the comamnd line. On Linux/Mac you should run `python3 -m pip install -r requirements.txt` in the terminal.

4. **Set up the postgresql database**

If you don't have postgresql installed you can [download it here](https://www.postgresql.org/download/).

Once you download postgresql you can set up the database using the following commands in the psql shell

```sql
CREATE ROLE highlight WITH LOGIN PASSWORD 'password';
CREATE DATABASE highlight OWNER highlight;
```

You can run psql with `psql` in the Windows command line or `sudo -u postgres psql` in the Linux/Mac terminal.

5. **Configure the bot**

Create a `config.py` file in directory where the bot is located. The file should look something like this.

 ```python
token = "xxxxxxxxxxxxxxxxxxxxxxxx.xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxx" # See https://discordpy.readthedocs.io/en/latest/discord.html#discord-intro
database_uri = "postgres://highlight:password@localhost/highlight" # Replace password with your password
console = 12345678912345678 # Channel ID of where to log errors and outdated packages
```

6. **Run the bot**

On Windows you can run `python bot.py` in the command line. On Linux/Mac you can run `python3 bot.py` in the terminal.

You need to keep the command running for the bot to stay online. If you can't run this on your own machine, I recommend getting a cheap VPS, and running the bot with a process manager like [systemd](https://en.wikipedia.org/wiki/Systemd).

If you are confused or need help, feel free to ask for help in the [support server](https://discord.gg/eHxvStNJb7).

# Requirements

- discord.py
- jishaku
- asyncpg
- dateparser
- humanize
- discord-ext-menus
