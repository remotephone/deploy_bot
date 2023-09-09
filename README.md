# Deploy Bot

A Discord bot that lets me deploy services to my swarm. I use this for chatop management of services in my swarm via discord chatops. I use static lists and checks where possible to avoid silliness. If you configure the TOTP secret, commands require a 2FA token to succeed.

## Details

This needs to run on a machine that has access to the docker socket. It will not work in a container unless you mount the socket and write your own Dockerfile.

You'll need to set up vars and handle secrets if you wanna use this.