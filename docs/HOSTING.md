# Hosting Callie so it stays online

Hosted mode turns Callie into a service people reach over the internet. It adds, only when switched on:

- **Invite-code sign-in** with a short agreement (Callie is an AI, how speech is processed, no recordings kept).
- **Separate data for every person**: contacts, schedule and memories are never shared.
- **Fair use**: one call at a time per person, a daily call-time allowance, and a cap on calls at once.
- **Sign out** and **Delete my data** in Settings.
- Your AI access keys stay on the server. Nobody who uses Callie ever sees them.

On your own computer none of this is active, and nothing about the desktop app changes.

## What it costs, honestly

- **There is no always-awake free hosting.** The 2026 comparisons I checked (September) put the cheapest always-on options at roughly **$2 to $5 a month**: a small Fly.io machine, or a small server from a provider such as Hetzner. Check the current price before you sign up.
- **Free plans that sleep when idle** (for example Render's free web service, which sleeps after about 15 minutes without visitors) are a poor fit: the first call after a quiet spell waits a minute while it wakes up.
- **A domain name** is about $10 a year. A free subdomain from a dynamic-DNS service also works.
- **The AI services' free tiers are meant for light use.** With more than a few regular people you will reach their limits. Keep `LIMIT_MINUTES_PER_DAY`, `CALLS_PER_DEVICE_PER_DAY` (5 by default) and `MAX_CONCURRENT_CALLS` modest, and plan to move to a paid plan when usage grows. At the prices I found in October, talking costs roughly ten cents per hour per caller.

## Path A (recommended): a small server with Docker

You need: a server running Ubuntu with at least 1 GB of memory (2 GB is comfortable), and a domain or subdomain.

1. **Create the server** at your chosen provider and note its IP address. In the provider's firewall allow only ports **22, 80 and 443**.
2. **Point your domain at it.** Add an `A` record, for example `callie.yourdomain.com`, to the server's IP address.
3. **Log in and install Docker:**
   ```bash
   ssh root@YOUR_SERVER_IP
   curl -fsSL https://get.docker.com | sh
   ```
4. **Get the code.** If the repository is private, use a GitHub access token in the address, or make the repository public.
   ```bash
   git clone https://github.com/muhumuza684/callie.git
   cd callie/deploy
   ```
5. **Fill in your settings:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Set `DOMAIN`, your `GROQ_API_KEY`, and `INVITE_CODES` (give each person or group their own code). Optional: `SUNBIRD_API_TOKEN` for Luganda.
6. **Start it:**
   ```bash
   docker compose up -d --build
   docker compose logs -f callie
   ```
   Caddy fetches the https certificate by itself once the domain points at the server.
7. **Open** `https://callie.yourdomain.com/login`, enter an invite code, and make a call from your phone.

**Updating:** `cd callie && git pull && cd deploy && docker compose up -d --build`

**New or removed invite codes:** edit `.env`, then run `docker compose up -d`.

**Backup** (everyone's data lives in one volume):
```bash
docker run --rm -v deploy_callie_data:/data -v "$PWD":/backup alpine tar czf /backup/callie-backup.tgz -C /data .
```

## Path B: Fly.io

`deploy/fly.toml` is a template. It keeps one machine awake and mounts a volume for the data. Check Fly's current documentation for names and prices, then:

```bash
fly launch --no-deploy --copy-config --dockerfile ../Dockerfile
fly volumes create callie_data --size 1
fly secrets set GROQ_API_KEY=... INVITE_CODES=code1,code2
fly deploy
```

## Rules to keep

- **Run one copy only.** Fair-use counters live in memory, so do not scale to several machines.
- **Https only.** Browsers refuse to use the microphone on plain http.
- **Secrets only in `.env`** (or `fly secrets`). Never commit them. The image never contains your `.env`.
- **Keep the data volume.** Rebuilding the container is safe; deleting the volume deletes everyone's data.
- **Look at the log** when something is wrong: `docker compose logs callie`, or `logs/callie.log` inside the data volume. People only ever see friendly messages; the details are here.

## Before you invite the public

1. **Register and tell people what you do with their data.** Uganda's Data Protection and Privacy Act 2019 expects organisations that handle personal data to register with the Personal Data Protection Office, and to be open about the services that process it. Write a privacy notice that names those services and where they process data, and take legal advice for users in the EU or US.
2. **Keep children out** until you have age checks and parental consent.
3. **Start small.** Begin with invite codes for a few testers, watch the log and the AI services' usage for a week, then widen.

## Troubleshooting

| What happens | What to check |
|---|---|
| "That code doesn't look right" | The code must be in `INVITE_CODES`. After editing `.env`, run `docker compose up -d` |
| The certificate never arrives | The domain's `A` record points at the server, and ports 80 and 443 are open |
| The microphone does not work | You must use the `https://` address |
| "Callie is busy right now" | `MAX_CONCURRENT_CALLS` is reached, or that person already has a call open |
| "You've reached today's call time" | `LIMIT_MINUTES_PER_DAY` is used up; it resets the next day |
| "You've used today's calls on this device" | `CALLS_PER_DEVICE_PER_DAY` is used up on that phone; it resets the next day |
| Contacts disappeared after an update | The data volume was removed. Restore from your backup |
