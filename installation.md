# Installation

If you have any issues with the installation process, feel free to ask for help in the [support server](https://discord.gg/eHxvStNJb7) on Discord.

1. **Download the bot as a Git repository**

If you don't have Git installed you can [download it here](https://git-scm.com/downloads).

Once you have Git installed, you can clone the bot by running `git clone https://github.com/ilovetocode2019/Highlight.git` in the command line or terminal.

2. **Download Python**

You can [download Python here](https://www.python.org/downloads/). You will need python 3.7+ to run the bot. Using Python 3.8 or 3.9 is recommended.

3. **Install required dependencies**

On windows you should run `py -m pip install -r requirements.txt` in the comamnd line. On Linux/Mac you should run `python3 -m pip install -r requirements.txt` in the terminal.

4. **Set up the postgresql database**

If you don't have postgresql installed you can [download it here](https://www.postgresql.org/download/).

Once you download postgresql you can set up the database using the following commands in the psql shell.

```sql
CREATE ROLE highlight WITH LOGIN PASSWORD 'PASSWORD HERE';
CREATE DATABASE highlight OWNER highlight;
```

You can run the psql shell using `psql` in the Windows command line or `sudo -u postgres psql` in the Linux/Mac terminal.

5. **Configure the bot**

Create a `config.py` file in directory where the bot is located. The file should look something like this.

```python
token = "TOKEN HERE" # See https://discordpy.readthedocs.io/en/latest/discord.html#discord-intro
database_uri = "postgres://highlight:password@localhost/highlight" # Replace password with your password
console = 12345678912345678 # Channel ID of where to log errors and outdated packages
```

More detailed instructions on confifguring the bot, can be found [here](/configuration).

6. **Run the bot**

On Windows you can run `py bot.py` in the command line. On Linux/Mac you can run `python3 bot.py` in the terminal.

You need to keep the command running for the bot to stay online. If you can't run this on your own machine, I recommend getting a cheap VPS, and running the bot with a process manager like [systemd](https://en.wikipedia.org/wiki/Systemd).

## What's Next

If your interested in configuring the bot further, see [configuration](/configuration).
