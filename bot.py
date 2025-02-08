import discord
import yaml
import docker
import random
import string
import psutil
import asyncio
from datetime import datetime, timedelta

# Discord Bot Setup
TOKEN = "YOUR_BOT_TOKEN"
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

# Allowed Users for `/deploy-win`
allowed_user_ids = [123456789012345678]  # Replace with your Discord user ID

# Active Containers
active_containers = {}

# Docker Client
docker_client = docker.from_env()

# Function to update docker-compose.yml
def update_docker_compose(username, password, ram, cpu, disk, disk2):
    with open("docker-compose.yml", "r") as file:
        compose_data = yaml.safe_load(file)

    # Update environment variables
    compose_data["services"]["windows"]["environment"]["USERNAME"] = username
    compose_data["services"]["windows"]["environment"]["PASSWORD"] = password
    compose_data["services"]["windows"]["environment"]["RAM_SIZE"] = f"{ram}G"
    compose_data["services"]["windows"]["environment"]["CPU_CORES"] = str(cpu)
    compose_data["services"]["windows"]["environment"]["DISK_SIZE"] = f"{disk}G"
    compose_data["services"]["windows"]["environment"]["DISK2_SIZE"] = f"{disk2}G"

    # Save updated config
    with open("docker-compose.yml", "w") as file:
        yaml.dump(compose_data, file, default_flow_style=False)

# Function to start a Windows container
def start_container(username, password, ram, cpu, disk, disk2):
    update_docker_compose(username, password, ram, cpu, disk, disk2)
    
    try:
        container = docker_client.containers.run(
            "dockurr/windows",
            detach=True,
            name=f"win_{username}",
            environment={
                "USERNAME": username,
                "PASSWORD": password,
                "RAM_SIZE": f"{ram}G",
                "CPU_CORES": str(cpu),
                "DISK_SIZE": f"{disk}G",
                "DISK2_SIZE": f"{disk2}G",
            },
            ports={"3389/tcp": None}
        )
        return container
    except Exception as e:
        return str(e)

# Slash command: Deploy Windows
@tree.command(name="deploy-win", description="Deploy a Windows container")
async def deploy_win(interaction: discord.Interaction, username: str, password: str):
    if interaction.user.id not in allowed_user_ids:
        await interaction.response.send_message("❌ You are not allowed to use this command.")
        return

    container = start_container(username, password, 4, 4, 400, 100)
    if isinstance(container, str):
        await interaction.response.send_message(f"❌ Failed to deploy: {container}")
    else:
        active_containers[container.name] = datetime.utcnow()
        await interaction.response.send_message(f"✅ Windows container `{container.name}` deployed!")

# Slash command: Setup default config
@tree.command(name="setup", description="Set default RAM, CPU, Disk sizes")
async def setup(interaction: discord.Interaction, ram: int, cpu: int, disk: int, disk2: int):
    update_docker_compose("default", "default", ram, cpu, disk, disk2)
    await interaction.response.send_message(f"✅ Default settings updated!")

# Slash command: Generate Promo Code
@tree.command(name="promo", description="Generate a promo code with resource limits")
async def promo(interaction: discord.Interaction, ram: int, cpu: int, disk: int, disk2: int):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    promo_codes[code] = {"ram": ram, "cpu": cpu, "disk": disk, "disk2": disk2}
    await interaction.response.send_message(f"✅ Promo code `{code}` created!")

# Slash command: List user containers
@tree.command(name="list", description="List your running Windows containers")
async def list_cmd(interaction: discord.Interaction):
    containers = [c.name for c in docker_client.containers.list() if c.name.startswith(f"win_{interaction.user.id}")]
    if containers:
        await interaction.response.send_message("\n".join(containers))
    else:
        await interaction.response.send_message("No running containers.")

# Slash command: Node Stats
@tree.command(name="node", description="Show system usage and active containers")
async def node(interaction: discord.Interaction):
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    containers = docker_client.containers.list()
    most_used = sorted(containers, key=lambda c: c.stats()["cpu_usage"], reverse=True)[:5]

    msg = f"🖥 **Node Stats**\n- CPU: {cpu}%\n- RAM: {ram}%\n"
    msg += "**Top Containers:**\n" + "\n".join([c.name for c in most_used])
    await interaction.response.send_message(msg)

# Slash command: Cleanup inactive containers
@tree.command(name="cleanup", description="Manually clean up inactive containers")
async def cleanup(interaction: discord.Interaction):
    now = datetime.utcnow()
    removed = 0

    for container_name, start_time in list(active_containers.items()):
        if (now - start_time) > timedelta(hours=8):
            docker_client.containers.get(container_name).remove(force=True)
            del active_containers[container_name]
            removed += 1

    await interaction.response.send_message(f"✅ Removed {removed} inactive containers.")

# Slash command: Port Forwarding
@tree.command(name="port_forward_win", description="Forward a Windows container port via Cloudflare Tunnel")
async def port_forward_win(interaction: discord.Interaction, container_name: str, port: int):
    tunnel_port = random.randint(1000, 9999)
    cmd = f"cloudflared tunnel --url http://localhost:{port} --name {container_name}"
    process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE)
    await process.communicate()

    await interaction.response.send_message(f"✅ Port {port} forwarded to `{tunnel_port}`")

# Slash command: Get Cloudflare URL
@tree.command(name="port_forward_win_url", description="Get Cloudflare Tunnel URL")
async def port_forward_win_url(interaction: discord.Interaction, container_name: str, port: int):
    url = f"https://{container_name}.example.com:{port}"  # Replace with real Cloudflare Tunnel URL
    await interaction.response.send_message(f"🔗 Access: {url}")

# Bot Startup
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

# Run the Bot
bot.run(TOKEN)
