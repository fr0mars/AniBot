import discord
from discord import app_commands
import requests
import json
from typing import List
import random

USER_FILE = "users.json"

def load_users() -> List[str]:
    try:
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_users(users: List[str]):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f)

class AnimeBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        
    async def setup_hook(self):
        await self.tree.sync()

client = AnimeBot()

@client.tree.command(name="register", description="Register your AniList username")
async def register(interaction: discord.Interaction, username: str):
    users = load_users()
    if username in users:
        await interaction.response.send_message(f"Username {username} is already registered!")
        return
    
    users.append(username)
    save_users(users)
    await interaction.response.send_message(f"Successfully registered {username}!")

@client.tree.command(name="remove", description="Remove a registered AniList username")
async def remove(interaction: discord.Interaction, username: str):
    users = load_users()
    if username not in users:
        await interaction.response.send_message(f"Username {username} is not registered!")
        return
    
    users.remove(username)
    save_users(users)
    await interaction.response.send_message(f"Successfully removed {username}!")

@client.tree.command(name="common", description="Find common planned anime between users")
@app_commands.describe(
    user1="First AniList username (optional)",
    user2="Second AniList username (optional)",
    user3="Third AniList username (optional)",
    user4="Fourth AniList username (optional)",
    user5="Fifth AniList username (optional)"
)
async def common(
    interaction: discord.Interaction, 
    user1: str = None, 
    user2: str = None, 
    user3: str = None,
    user4: str = None,
    user5: str = None
):
    query_username_planning = '''
    query ($username: String) {
        MediaListCollection(userName: $username, type: ANIME, status: PLANNING) {
            lists {
                entries {
                    media {
                        id
                        title {
                            romaji
                            english
                            native
                        }
                        coverImage {
                            large
                        }
                        genres
                        averageScore
                    }
                }
            }
        }
    }
    '''
    
    url = 'https://graphql.anilist.co'
    
    users = [u for u in [user1, user2, user3, user4, user5] if u] if any([user1, user2, user3, user4, user5]) else load_users()
    
    if len(users) < 2:
        await interaction.response.send_message("Need at least 2 users to find common anime!")
        return
    
    await interaction.response.send_message(f"Looking for common anime between: {', '.join(users)}...")
    
    animes = []
    anime_details = {}
    for user in users:
        planning_ids = []
        variables = {'username': user}
        response = requests.post(url, json={'query': query_username_planning, 'variables': variables}).json()
        
        if 'errors' in response:
            await interaction.followup.send(f"Error fetching data for user {user}")
            return
            
        if len(response['data']['MediaListCollection']['lists']) == 0:
            continue
            
        for media in response['data']['MediaListCollection']['lists'][0]['entries']:
            planning_ids.append(media['media']['id'])
            anime_details[media['media']['id']] = media['media']
        animes.append(planning_ids)
    
    common_animes = set(animes[0])
    for anime_list in animes[1:]:
        common_animes.intersection_update(anime_list)
    
    if not common_animes:
        await interaction.followup.send("No common anime found in planning lists!")
        return

    embed = discord.Embed(
        title="Common Planned Anime",
        description=f"Found {len(common_animes)} anime in common between {', '.join(users)}",
        color=discord.Color.from_rgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    )

    for anime_id in common_animes:
        anime = anime_details[anime_id]
        title = anime['title']['romaji']
        genres = ', '.join(anime['genres'][:3])
        score = anime['averageScore'] or 'N/A'
        
        value = f"**Genres:** {genres}\n**Score:** {score}"
        embed.add_field(name=title, value=value, inline=False)

    if common_animes:
        first_anime = anime_details[list(common_animes)[0]]
        if first_anime['coverImage']['large']:
            embed.set_thumbnail(url=first_anime['coverImage']['large'])

    await interaction.followup.send(embed=embed)
stats_query = '''
query User($username: String) {
  User(name: $username) {
    statistics {
      anime {
        meanScore
        count
        episodesWatched
        minutesWatched
        genres {
          genre
          count
          meanScore
        }
        releaseYears {
          count
          minutesWatched
        }
      }
    }
  }
}
'''

@client.tree.command(name="stats", description="Show detailed anime statistics for a user")
async def stats(interaction: discord.Interaction, username: str):
    variables = {'username': username}
    url = 'https://graphql.anilist.co'
    
    await interaction.response.send_message(f"Fetching stats for {username}...")
    
    response = requests.post(url, json={'query': stats_query, 'variables': variables}).json()
    
    if 'errors' in response:
        await interaction.followup.send(f"Error fetching data for user {username}: {response['errors']}")
        return
        
    stats = response['data']['User']['statistics']['anime']

    
    main_embed = discord.Embed(
        title=f"📊 Anime Statistics for {username}",
        color=discord.Color.blue()
    )
    
    
    total_time = stats['minutesWatched']
    days = total_time // (24 * 60)
    hours = (total_time % (24 * 60)) // 60
    minutes = total_time % 60
    

    main_embed.add_field(
        name="📈 Overview",
        value=f"Mean Score: **{stats['meanScore']}**\n"
              f"Total Anime: **{stats['count']}**\n"
              f"Episodes Watched: **{stats['episodesWatched']}**\n"
              f"Time Watched: **{days}d {hours}h {minutes}m**",
        inline=False
    )
    
    
    genres_embed = discord.Embed(
        title="Genre Distribution",
        color=discord.Color.green()
    )
    
    
    sorted_genres = sorted(stats['genres'], key=lambda x: x['count'], reverse=True)[:10]
    for genre in sorted_genres:
        genres_embed.add_field(
            name=genre['genre'],
            value=f"Count: **{genre['count']}**\nMean Score: **{genre['meanScore']}**",
            inline=True
        )
    
    """
    # Create Release Years Embed
    years_embed = discord.Embed(
        title="Yearly Distribution",
        description="Top anime years by count",
        color=discord.Color.gold()
    )
    
    # Sort years by count
    sorted_years = sorted(stats['releaseYears'], key=lambda x: x['count'], reverse=True)[:10]
    for year in sorted_years:
        years_embed.add_field(
            name=str(year['year']),
            value=f"Count: **{year['count']}**\nMinutes Watched: **{year['minutesWatched']}**",
            inline=True
        )
    """
    await interaction.followup.send(embeds=[main_embed, genres_embed])

client.run('YOUR_DISCORD_BOT_TOKEN')

