import json
import logging
import os
import subprocess

import discord
import pyotp
import yaml
from discord.ext import commands
from pytablewriter import MarkdownTableWriter


class JsonFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            message = json.loads(record.getMessage())
        else:
            message = record.getMessage()

        log_dict = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "path": record.pathname,
            "line": record.lineno,
        }
        return json.dumps(log_dict)


deploy_logger = logging.getLogger("deploy_bot_logger")
deploy_logger.setLevel(logging.DEBUG)
fhandler = logging.FileHandler(filename="deploy_bot.log", encoding="utf-8", mode="w")
fhandler.setFormatter(JsonFormatter())
fhandler.setLevel(logging.ERROR)
shandler = logging.StreamHandler()
shandler.setFormatter(JsonFormatter())
shandler.setLevel(logging.INFO)
deploy_logger.addHandler(fhandler)
deploy_logger.addHandler(shandler)

TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents(messages=True, guilds=True, message_content=True)
bot = discord.ext.commands.Bot(intents=intents, command_prefix=".")


## Helpers


def deploy_docker_stack_on_host(service):
    deploy_logger.info(f"Verifying request to deploy {service}!")
    # run a shell command to deploy a docker serviceif the name is a key in the dict
    base_command = "docker stack deploy"
    with open("/opt/deploy_bot/services.yml") as f:
        services = yaml.safe_load(f)
    if service in services.keys():
        if services[service]["with_reg_auth"]:
            base_command += " --with-registry-auth"
        if services[service]["remove_first"]:
            base_command = f"docker service rm {services[service]['service_name']} && {base_command}"
        base_command += f" -c {services[service]['compose_file']} {services[service]['service_name']}"
        deploy_logger.info(f"Running command: {base_command}")
        output = subprocess.run(base_command.split(), stdout=subprocess.PIPE)
        message = f'return_code={output.returncode} stdout="{output.stdout.decode()}"'
        if output.returncode != 0:
            deploy_logger.error(message)
        else:
            deploy_logger.info(message)
        return output.stdout.decode()
    else:
        deploy_logger.error(f"{service} not found in services.yml")
        return "Service not found"


def get_docker_service_logs(service):
    base_command = f"docker service logs {service}"
    output = subprocess.run(base_command.split(), stdout=subprocess.PIPE)
    message = {"return_code": output.returncode, "stdout": output.stdout.decode()}
    if output.returncode != 0:
        deploy_logger.error(message)
    else:
        deploy_logger.info(message)
    return output.stdout


def get_running_containers(service):
    base_command = (
        f"docker service ps {service} --filter desired-state=running --format json"
    )
    output = subprocess.run(base_command.split(), stdout=subprocess.PIPE)
    message = {"return_code": output.returncode, "stdout": output.stdout.decode()}
    if output.returncode != 0:
        deploy_logger.error(message)
    else:
        deploy_logger.info(message)
    return output.stdout


## End Helpers


@bot.event
async def on_ready():
    deploy_logger.info("deploy_bot has connected to Discord!")


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"This command is on a {int(error.retry_after)} second cooldown, please wait"
        )
    deploy_logger.info(
        error
    )  # re-raise the error so all the errors will still show up in console


def validate_totp(totp: str) -> bool:
    verifier = pyotp.TOTP(os.environ["TOTP_SECRET"])
    return verifier.verify(totp)


@bot.command(
    name="deploy",
    help="deploy a service that's already running. Must be defined in the services.yml file and requires 2FA",
)
@commands.cooldown(1, 10, commands.BucketType.user)
async def deploy_service(
    ctx: commands.Context,
    service: str = commands.parameter(
        default=None,
        description="A name of a service to deploy. Will require 2FA",
    ),
    totp: str = commands.parameter(
        default=None,
        description="A 6 digit TOTP code",
    ),
):
    if not service or not totp:
        missing_params = [x for x in [service, totp] if x is None]
        deploy_logger.error(
            f"{ctx.message.author} did not provide a {', '.join(missing_params)}"
        )
        await ctx.send("You must provide a service name and totp code.")
    else:
        if validate_totp(totp):
            deploy_logger.info(f"{ctx.message.author} tried to deploy {service}")
            result = deploy_docker_stack_on_host(service)
            await ctx.send(result)
        else:
            deploy_logger.error(f"{ctx.message.author} provided an invalid totp code")
            await ctx.send("Invalid TOTP code, please try again")


@bot.command(
    name="get_logs",
    help="get the logs of a service that's already running. Must be defined in the services.yml file",
)
@commands.cooldown(1, 10, commands.BucketType.user)
@commands.is_owner()
async def get_service_logs(
    ctx: commands.Context,
    service: str = commands.parameter(
        default=None,
        description="A name of a service to get logs for. Will require 2FA",
    ),
):
    if not service:
        deploy_logger.error(f"{ctx.message.author} did not provide a service name")
        await ctx.send("You must provide a service name.")
    else:
        deploy_logger.info(f"{ctx.message.author} requested logs for {service}")
        result = get_docker_service_logs(service)
        # get last 1950 characters of string
        result = result.decode("utf-8")[-1930:]
        await ctx.send(
            f"Last 2000ish characters of logs for {service}:\n```{result}```"
        )


@bot.command(
    name="services",
    help="List all services that can be deployed. Reads from thes ervices.yml file",
)
@commands.cooldown(1, 10, commands.BucketType.user)
async def list_services(ctx: commands.Context):
    deploy_logger.info(f"{ctx.message.author} requested a list of services")
    with open("/opt/deploy_bot/services.yml") as f:
        services = yaml.safe_load(f)
    await ctx.send(f"Services that can be deployed: {', '.join(services.keys())}")


@bot.command(name="get_nodes", help="list all available nodes")
@commands.cooldown(1, 10, commands.BucketType.user)
async def list_nodes(ctx: commands.Context):
    deploy_logger.info(f"{ctx.message.author} requested a list of nodes")
    try:
        command = "docker node ls --format json"
        result = subprocess.run(command.split(), stdout=subprocess.PIPE)
        nodes = [json.loads(x) for x in result.stdout.decode("utf-8").splitlines()]
        writer = MarkdownTableWriter(table_name="Docker Nodes Status")
        writer.headers = ["Hostname", "Status", "Availability", "Manager Status"]
        writer.value_matrix = [
            [x["Hostname"], x["Status"], x["Availability"], x["ManagerStatus"]]
            for x in nodes
        ]
        table = writer.dumps()
        await ctx.send(f"```\n{table}\n```")
    except Exception as e:
        deploy_logger.error(e)
        return "Something went wrong"


@bot.command(name="get_services", help="list all available services")
@commands.cooldown(1, 10, commands.BucketType.user)
async def get_docker_services(ctx: commands.Context):
    deploy_logger.info(f"{ctx.message.author} requested a list of services")
    try:
        command = "docker service ls --format json"
        result = subprocess.run(command.split(), stdout=subprocess.PIPE)
        services = [json.loads(x) for x in result.stdout.decode("utf-8").splitlines()]
        writer = MarkdownTableWriter(table_name="Docker Services Status")
        writer.headers = ["ID", "Name", "Replicas"]
        writer.value_matrix = [[x["ID"], x["Name"], x["Replicas"]] for x in services]
        table = writer.dumps()
        await ctx.send(f"```\n{table}\n```")
    except Exception as e:
        deploy_logger.error(e)
        return "Something went wrong"


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
