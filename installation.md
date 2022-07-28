---
layout: default
nav_order: 2
---

# Installation

This is bot is not being supported anymore. These instructions likely still work, however the bot will eventually break and any issues you have will not be fixed.
{: .note }

1. **Clone the bot as a Git repository**

    If you don't have Git installed you can [download it here](https://git-scm.com/downloads).

    Once you have Git installed, you can clone the bot by running `git clone https://github.com/ilovetocode2019/Highlight.git` in the command line or terminal.

2. **Download Python**

    If you don't have python already installed you can [download it here](https://www.python.org/downloads/). You will need python 3.7+ to run the bot. Using Python 3.8 or 3.9 is recommended.

    Make sure to include Pip (the Python package manager) with the installation. You can also see [this page](https://pip.pypa.io/en/latest/installing/) for instructions on installing Pip.
    {: .note }

3. **Install required dependencies**

    On windows you should run `py -m pip install -U pip -r requirements.txt` in the comamnd line. On Linux/Mac you should run `python3 -m pip install -U pip -r requirements.txt` in the terminal.

4. **Setup the postgresql database**

    If you don't have postgresql installed you can [download it here](https://www.postgresql.org/download/).

    Once you download postgresql you can set up the database using the following commands in the psql shell.

    ```sql
    CREATE ROLE highlight WITH LOGIN PASSWORD 'PASSWORD HERE';
    CREATE DATABASE highlight OWNER highlight;
    ```

    You can run the psql shell using `psql` in the Windows command line or `sudo -u postgres psql` in the Linux/Mac terminal.

5. **Configure the bot**

    Create a `config.yml` file in the directory where the bot is located. The file should look something like this:

    ```yml
    token: "TOKEN HERE"
    database-uri: "postgres://highlight:PASSWORD HERE@localhost/highlight"
    auto-update: true
    ```

    More detailed instructions on confifguring the bot, can be found [here](configuration).

6. **Run the bot**

    On Windows you can run `py bot.py` in the command line. On Linux/Mac you can run `python3 bot.py` in the terminal.

    You need to keep running the bot in order to keep it online. If you can't run it on your own machine, I recommend renting a cheap VPS, and running the bot with a process manager like [systemd](https://en.wikipedia.org/wiki/Systemd).
    {: .note }

## What's Next?

If your interested in configuring the bot further, see the [configuration instructions](configuration). You can also checkout the command list [here](commands).
