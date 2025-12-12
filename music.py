"""
This example cog demonstrates basic usage of Lavalink.py, using the DefaultPlayer.
As this example primarily showcases usage in conjunction with discord.py, you will need to make
modifications as necessary for use with another Discord library.

Usage of this cog requires Python 3.6 or higher due to the use of f-strings.
Compatibility with Python 3.5 should be possible if f-strings are removed.
"""
import re

import discord
from discord.ext import commands

import asyncio

import lavalink
from discord.ext import commands
from lavalink.events import TrackStartEvent, QueueEndEvent
from lavalink.errors import ClientError
from lavalink.server import LoadType

url_rx = re.compile(r'https?://(?:www\.)?.+')

class LavalinkVoiceClient(discord.VoiceProtocol):
    """
    This is the preferred way to handle external voice sending
    This client will be created via a cls in the connect method of the channel
    see the following documentation:
    https://discordpy.readthedocs.io/en/latest/api.html#voiceprotocol
    """

    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.guild_id = channel.guild.id
        self._destroyed = False

        if not hasattr(self.client, 'lavalink'):
            # Instantiate a client if one doesn't exist.
            # We store it in `self.client` so that it may persist across cog reloads,
            # however this is not mandatory.
            self.client.lavalink = lavalink.Client(client.user.id)
            self.client.lavalink.add_node(host='localhost', port=2333, password='youshallnotpass',
                                          region='us', name='default-node')

        # Create a shortcut to the Lavalink client here.
        self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {
            't': 'VOICE_SERVER_UPDATE',
            'd': data
        }

        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        channel_id = data['channel_id']

        if not channel_id:
            await self._destroy()
            return

        self.channel = self.client.get_channel(int(channel_id))

        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {
            't': 'VOICE_STATE_UPDATE',
            'd': data
        }

        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = False, self_mute: bool = False) -> None:
        """
        Connect the bot to the voice channel and create a player_manager
        if it doesn't exist yet.
        """
        # ensure there is a player_manager when creating a new voice_client
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(channel=self.channel, self_mute=False, self_deaf=True)

    async def disconnect(self, *, force: bool = False) -> None:
        """
        Handles the disconnect.
        Cleans up running player and leaves the voice client.
        """
        player = self.lavalink.player_manager.get(self.channel.guild.id)

        # no need to disconnect if we are not connected
        if not force and not player.is_connected:
            return

        # None means disconnect
        await self.channel.guild.change_voice_state(channel=None)

        # update the channel_id of the player to None
        # this must be done because the on_voice_state_update that would set channel_id
        # to None doesn't get dispatched after the disconnect
        player.channel_id = None
        await self._destroy()

    async def _destroy(self):
        self.cleanup()

        if self._destroyed:
            # Idempotency handling, if `disconnect()` is called, the changed voice state
            # could cause this to run a second time.
            return

        self._destroyed = True

        try:
            await self.lavalink.player_manager.destroy(self.guild_id)
        except ClientError:
            pass


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Initializes the Lavalink client only AFTER the bot has successfully logged in
        and bot.user is available.
        """
        # We only need to initialize if it hasn't been done yet (e.g., across reloads)
        if not hasattr(self.bot, 'lavalink'):
            # The bot.user object is now guaranteed to exist!
            self.bot.lavalink = lavalink.Client(self.bot.user.id)
            self.bot.lavalink.add_node(host='lava-v4.ajieblogs.eu.org', port=443, password='https://dsc.gg/ajidevserver', region='eu', name='ajie-node', ssl=True)

        self.lavalink = self.bot.lavalink # Set the local reference
        self.lavalink.add_event_hooks(self)
        print("Lavalink Client Initialized and ready to connect nodes.") # Optional: Confirmation message

        # Removed because that was causing the events to not work properly
        # self.lavalink._event_hooks.clear()


    @lavalink.listener(TrackStartEvent)
    async def on_track_start(self, event: TrackStartEvent):
        guild_id = event.player.guild_id
        guild = self.bot.get_guild(guild_id)

        if not guild:
            return await self.lavalink.player_manager.destroy(guild_id)


    @lavalink.listener(QueueEndEvent)
    async def on_queue_end(self, event: QueueEndEvent):
        guild_id = event.player.guild_id
        guild = self.bot.get_guild(guild_id)

        if guild is not None:
            await guild.voice_client.disconnect(force=True)

    async def create_player(ctx: commands.Context):
        """
        A check that is invoked before any commands marked with `@commands.check(create_player)` can run.

        This function will try to create a player for the guild associated with this Context, or raise
        an error which will be relayed to the user if one cannot be created.
        """
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        player = ctx.bot.lavalink.player_manager.create(ctx.guild.id)
        # Create returns a player if one exists, otherwise creates.
        # This line is important because it ensures that a player always exists for a guild.

        # Most people might consider this a waste of resources for guilds that aren't playing, but this is
        # the easiest and simplest way of ensuring players are created.

        # These are commands that require the bot to join a voicechannel (i.e. initiating playback).
        # Commands such as volume/skip etc don't require the bot to be in a voicechannel so don't need listing here.
        should_connect = ctx.command.name in ('play',)

        voice_client = ctx.voice_client

        if not ctx.author.voice or not ctx.author.voice.channel:
            # Check if we're in a voice channel. If we are, tell the user to join our voice channel.
            if voice_client is not None:
                raise commands.CommandInvokeError('Você precisa entrar no meu canal de voz primeiro.')

            # Otherwise, tell them to join any voice channel to begin playing music.
            raise commands.CommandInvokeError('Entre num canal de voz primeiro.')

        voice_channel = ctx.author.voice.channel

        if voice_client is None:
            if not should_connect:
                raise commands.CommandInvokeError("Eu não estou tocando uma música.")

            permissions = voice_channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:
                raise commands.CommandInvokeError('Eu preciso das permissões `CONECTAR` and `FALAR`')

            if voice_channel.user_limit > 0:
                # A limit of 0 means no limit. Anything higher means that there is a member limit which we need to check.
                # If it's full, and we don't have "move members" permissions, then we cannot join it.
                if len(voice_channel.members) >= voice_channel.user_limit and not ctx.me.guild_permissions.move_members:
                    raise commands.CommandInvokeError('Seu canal de voz está cheio!')

            player.store('channel', ctx.channel.id)
            await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)
        elif voice_client.channel.id != voice_channel.id:
            raise commands.CommandInvokeError('Você precisa estar no canal de voz.')

        return True


    @commands.command(aliases=['tocar'])
    @commands.check(create_player)
    async def play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        # Get the player for this guild from cache.
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        # Remove leading and trailing <>. <> may be used to suppress embedding links in Discord.
        query = query.strip('<>')

        # Check if the user input might be a URL. If it isn't, we can Lavalink do a YouTube search for it instead.
        # SoundCloud searching is possible by prefixing "scsearch:" instead.
        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        # Get the results for the query from Lavalink.
        results = await player.node.get_tracks(query)

        embed = discord.Embed(color=discord.Colour.orange())

        # Valid load_types are:
        #   TRACK    - direct URL to a track
        #   PLAYLIST - direct URL to playlist
        #   SEARCH   - query prefixed with either "ytsearch:" or "scsearch:". This could possibly be expanded with plugins.
        #   EMPTY    - no results for the query (result.tracks will be empty)
        #   ERROR    - the track encountered an exception during loading
        if results.load_type == LoadType.EMPTY:
            return await ctx.send("Não consegui encontrar nenhuma faixa para essa pesquisa.")
        elif results.load_type == LoadType.PLAYLIST:
            tracks = results.tracks

            # Add all of the tracks from the playlist to the queue.
            for track in tracks:
                # requester isn't necessary but it helps keep track of who queued what.
                # You can store additional metadata by passing it as a kwarg (i.e. key=value)
                # Requester can be set with `track.requester = ctx.author.id`. Any other extra attributes
                # must be set via track.extra.
                track.extra["requester"] = ctx.author.id
                player.add(track=track)

            embed.title = '✅ Playlist adicionada!'
            embed.description = f'{results.playlist_info.name} - {len(tracks)} tracks'
        else:
            track = results.tracks[0]
            embed.title = '✅ Faixa adicionada na fila.'
            embed.description = f'[{track.title}]({track.uri})'

            # requester isn't necessary but it helps keep track of who queued what.
            # You can store additional metadata by passing it as a kwarg (i.e. key=value)
            # Requester can be set with `track.requester = ctx.author.id`. Any other extra attributes
            # must be set via track.extra.
            track.extra["requester"] = ctx.author.id

            player.add(track=track)

        await ctx.send(embed=embed)

        # We don't want to call .play() if the player is playing as that will effectively skip
        # the current track.
        if not player.is_playing:
            await player.play()

    @commands.command(aliases=['l', 'sair'])
    @commands.check(create_player)
    async def leave(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        # The necessary voice channel checks are handled in "create_player."
        # We don't need to duplicate code checking them again.

        # Clear the queue to ensure old tracks don't start playing
        # when someone else queues something.
        player.queue.clear()
        # Stop the current track so Lavalink consumes less resources.
        await player.stop()
        # Disconnect from the voice channel.
        await ctx.voice_client.disconnect(force=True)
        await ctx.send(' 👋 | Fui retirada da call.')

    @commands.command(aliases=['s', 'pular'])
    async def skip(self, ctx):
        """ Plays the next track in the queue, if any. """

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.skip()

    @commands.check(create_player)
    @commands.command(alises=['parar'])
    async def stop(self, ctx):
        """ Stop the music and clears the queue. """

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.queue.clear()
        await player.stop()

        await ctx.voice_client.disconnect(force=True)

    @commands.command(aliases=['pausar'])
    async def pause(self, ctx):
        """ Sets the player's paused state. """
        
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.set_pause(pause=True)

    @commands.command(alias=['continuar'])
    async def resume(self, ctx):
        """ Sets the player's resume state. """

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.set_pause(pause=False)

    @commands.check(create_player)
    @commands.command()
    async def volume(self, ctx, level : float | int):
        """ Sets the player's volume """

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        def check(level):
            print(f"value of level is: {level}")

            if level > 0 and level <= 1:
                return True
            else:
                return False

        if check(level):
            await player.set_volume(int(level * 100))
        else:
            await ctx.send("> ⚠️ **Erro**: você só pode colocar valores **acima de 0** e **até 1**, sendo 1 o valor padrão.")


    @commands.check(create_player)
    @commands.command()
    async def loop(self, ctx): 
        """ Sets the player's loop mode on or off"""

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if player.loop == player.LOOP_NONE:
            player.set_loop(1)
            await ctx.send(" > ✅ Modo loop foi ativado.")
        else:
            player.set_loop(0)
            await ctx.send(" > ✅ Modo loop foi desativado.")


def setup(bot):
    bot.add_cog(Music(bot))