#!/usr/bin/env tsx
import { execSync } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';
import readline from 'readline';

// ── ANSI helpers ────────────────────────────────────────────────────────────
const c = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  bgBlack: '\x1b[40m',
  gray: '\x1b[90m',
};

const PROJECT_ROOT = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '..',
);

// ── Banner ──────────────────────────────────────────────────────────────────
const BANNER = `
 ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗
██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝
██║     ██║     ███████║██║   ██║██║  ██║█████╗
██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝
╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝╚══════╝

 ██████╗██╗      █████╗ ██╗    ██╗
██╔════╝██║     ██╔══██╗██║    ██║
██║     ██║     ███████║██║ █╗ ██║
██║     ██║     ██╔══██║██║███╗██║
╚██████╗███████╗██║  ██║╚███╔███╔╝
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝
`;

// ── Utilities ───────────────────────────────────────────────────────────────

function spinner(
  label: string,
): { stop: (status: 'ok' | 'fail' | 'warn', msg?: string) => void } {
  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  let i = 0;
  const iv = setInterval(() => {
    process.stdout.write(
      `\r  ${c.cyan}${frames[i++ % frames.length]}${c.reset}  ${label}   `,
    );
  }, 80);
  return {
    stop(status, msg) {
      clearInterval(iv);
      const icon =
        status === 'ok'
          ? `${c.green}✓${c.reset}`
          : status === 'warn'
            ? `${c.yellow}⚠${c.reset}`
            : `${c.red}✗${c.reset}`;
      process.stdout.write(`\r  ${icon}  ${msg ?? label}\n`);
    },
  };
}

// Single shared readline interface — never create more than one.
// Creating a new rl per question corrupts stdin state and silently drops
// pasted input after the first close().
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: true,
});

async function ask(question: string, defaultVal?: string): Promise<string> {
  return new Promise((resolve) => {
    const prompt = defaultVal
      ? `  ${c.bold}${question}${c.reset} ${c.gray}(${defaultVal})${c.reset} › `
      : `  ${c.bold}${question}${c.reset} › `;
    rl.question(prompt, (ans) => {
      resolve(ans.trim() || defaultVal || '');
    });
  });
}

function section(title: string) {
  console.log();
  console.log(`  ${c.bold}${c.white}${title}${c.reset}`);
  console.log(`  ${c.gray}${'─'.repeat(title.length)}${c.reset}`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseEnvFile(filePath: string): Record<string, string> {
  const result: Record<string, string> = {};
  let content: string;
  try {
    content = fs.readFileSync(filePath, 'utf-8');
  } catch {
    return result;
  }
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    let value = trimmed.slice(eqIdx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value) result[key] = value;
  }
  return result;
}

async function validateBotToken(
  token: string,
): Promise<{ valid: boolean; username?: string; id?: number }> {
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/getMe`);
    const data = (await res.json()) as {
      ok: boolean;
      result?: { username?: string; id?: number };
    };
    if (data.ok && data.result) {
      return {
        valid: true,
        username: data.result.username,
        id: data.result.id,
      };
    }
    return { valid: false };
  } catch {
    return { valid: false };
  }
}

// ── Main ────────────────────────────────────────────────────────────────────

async function main() {
  // ── Step 1: Banner ──
  console.log(`${c.cyan}${c.bold}${BANNER}${c.reset}`);
  console.log(`  ${c.gray}Your Claude Code CLI. In your pocket.${c.reset}`);
  console.log(`  ${c.gray}v1.0.0 · Setup Wizard${c.reset}`);
  console.log();
  const termWidth = process.stdout.columns || 80;
  console.log(`  ${c.gray}${'─'.repeat(termWidth - 4)}${c.reset}`);
  console.log();
  console.log(
    `  Welcome. Let's get ClaudeClaw running in a few minutes.`,
  );
  console.log(`  Press Ctrl+C at any time to exit.`);

  // ── Step 2: System Checks ──
  section('System Checks');

  // Node version
  const s1 = spinner('Checking Node.js version...');
  await sleep(400);
  const nodeVersion = process.version;
  const nodeMajor = parseInt(nodeVersion.slice(1).split('.')[0], 10);
  if (nodeMajor >= 20) {
    s1.stop('ok', `Node ${nodeVersion}`);
  } else {
    s1.stop('fail', `Node 20+ required, you have ${nodeVersion}`);
    process.exit(1);
  }

  // Claude CLI
  const s2 = spinner('Checking Claude CLI...');
  await sleep(400);
  try {
    execSync('which claude', { stdio: 'pipe' });
    let claudeVersion = 'installed';
    try {
      claudeVersion = execSync('claude --version', { stdio: 'pipe' })
        .toString()
        .trim();
    } catch {
      // version check failed but cli exists
    }
    s2.stop('ok', `Claude CLI ${c.gray}${claudeVersion}${c.reset}`);
  } catch {
    s2.stop('fail', 'Claude CLI not found. Install: npm i -g @anthropic-ai/claude-code');
    process.exit(1);
  }

  // .env file
  const envPath = path.join(PROJECT_ROOT, '.env');
  const s3 = spinner('Checking .env file...');
  await sleep(300);
  const envExists = fs.existsSync(envPath);
  if (envExists) {
    s3.stop('ok', '.env file found');
  } else {
    s3.stop('warn', 'Will create .env from template');
  }

  // ── Step 3: Load or create .env ──
  const env: Record<string, string> = envExists ? parseEnvFile(envPath) : {};

  // ── Step 4: Telegram Bot Token ──
  section('── Telegram ────────────────────────────────────');

  let botUsername = '';
  let botId = 0;

  if (env.TELEGRAM_BOT_TOKEN) {
    const s4 = spinner('Validating bot token...');
    await sleep(300);
    const result = await validateBotToken(env.TELEGRAM_BOT_TOKEN);
    if (result.valid) {
      botUsername = result.username || '';
      botId = result.id || 0;
      s4.stop(
        'ok',
        `Bot: @${botUsername} (ID: ${botId})`,
      );
    } else {
      s4.stop('fail', "Invalid token — let's get a new one");
      delete env.TELEGRAM_BOT_TOKEN;
    }
  }

  if (!env.TELEGRAM_BOT_TOKEN) {
    console.log();
    console.log(`  ${c.gray}1. Open Telegram and search for @BotFather${c.reset}`);
    console.log(`  ${c.gray}2. Send /newbot${c.reset}`);
    console.log(`  ${c.gray}3. Follow the prompts to name your bot${c.reset}`);
    console.log(`  ${c.gray}4. Copy the token BotFather gives you${c.reset}`);
    console.log();

    let valid = false;
    while (!valid) {
      const token = await ask('Paste your bot token');
      if (!token) {
        console.log(`  ${c.red}Token is required.${c.reset}`);
        continue;
      }
      const sv = spinner('Validating...');
      const result = await validateBotToken(token);
      if (result.valid) {
        env.TELEGRAM_BOT_TOKEN = token;
        botUsername = result.username || '';
        botId = result.id || 0;
        sv.stop('ok', `Bot: @${botUsername} (ID: ${botId})`);
        valid = true;
      } else {
        sv.stop('fail', 'Invalid token. Try again.');
      }
    }
  }

  // ── Step 5: Allowed Chat ID ──
  console.log();
  if (env.ALLOWED_CHAT_ID) {
    console.log(
      `  ${c.green}✓${c.reset}  Locked to chat: ${env.ALLOWED_CHAT_ID}`,
    );
  } else {
    console.log(`  ${c.gray}To get your chat ID:${c.reset}`);
    console.log(
      `  ${c.gray}1. Open Telegram and message your bot${c.reset}`,
    );
    console.log(`  ${c.gray}2. Send /chatid${c.reset}`);
    console.log(
      `  ${c.gray}3. Copy the number it replies with${c.reset}`,
    );
    console.log();
    console.log(
      `  ${c.gray}Or press Enter to skip for now (bot will prompt you on first message)${c.reset}`,
    );
    console.log();

    const chatId = await ask('Your Telegram chat ID', 'skip');
    if (chatId !== 'skip') {
      env.ALLOWED_CHAT_ID = chatId;
    }
  }

  // ── Step 6: Voice (Optional) ──
  section('── Voice (Optional) ────────────────────────────');

  console.log();
  console.log(
    `  ${c.gray}Voice lets you send voice notes and hear responses in your own voice.${c.reset}`,
  );
  console.log(
    `  ${c.gray}Requires: Groq API key (free) + ElevenLabs API key + your Voice ID${c.reset}`,
  );
  console.log();

  // Groq
  if (env.GROQ_API_KEY) {
    console.log(`  ${c.green}✓${c.reset}  Groq STT configured`);
  } else {
    const groqKey = await ask(
      'Groq API key (get free at console.groq.com, Enter to skip)',
    );
    if (groqKey) {
      env.GROQ_API_KEY = groqKey;
    }
  }

  // ElevenLabs
  if (env.ELEVENLABS_API_KEY && env.ELEVENLABS_VOICE_ID) {
    console.log(`  ${c.green}✓${c.reset}  ElevenLabs TTS configured`);
  } else {
    if (!env.ELEVENLABS_API_KEY) {
      const elKey = await ask(
        'ElevenLabs API key (get at elevenlabs.io, Enter to skip)',
      );
      if (elKey) {
        env.ELEVENLABS_API_KEY = elKey;
      }
    }
    if (env.ELEVENLABS_API_KEY && !env.ELEVENLABS_VOICE_ID) {
      const voiceId = await ask('ElevenLabs Voice ID (Enter to skip)');
      if (voiceId) {
        env.ELEVENLABS_VOICE_ID = voiceId;
      }
    }
  }

  // ── Step 7: Write .env ──
  console.log();
  const s7 = spinner('Saving configuration...');
  await sleep(400);

  const envContent = `# ClaudeClaw Configuration
# Generated by setup wizard

TELEGRAM_BOT_TOKEN=${env.TELEGRAM_BOT_TOKEN || ''}
ALLOWED_CHAT_ID=${env.ALLOWED_CHAT_ID || ''}

# Voice
GROQ_API_KEY=${env.GROQ_API_KEY || ''}
ELEVENLABS_API_KEY=${env.ELEVENLABS_API_KEY || ''}
ELEVENLABS_VOICE_ID=${env.ELEVENLABS_VOICE_ID || ''}
`;

  fs.writeFileSync(envPath, envContent, 'utf-8');

  // Immediately verify what was written — catch any silent failures
  const written = parseEnvFile(envPath);
  const missingAfterWrite: string[] = [];
  if (env.TELEGRAM_BOT_TOKEN && !written.TELEGRAM_BOT_TOKEN) missingAfterWrite.push('TELEGRAM_BOT_TOKEN');
  if (env.ALLOWED_CHAT_ID && !written.ALLOWED_CHAT_ID) missingAfterWrite.push('ALLOWED_CHAT_ID');
  if (env.GROQ_API_KEY && !written.GROQ_API_KEY) missingAfterWrite.push('GROQ_API_KEY');
  if (env.ELEVENLABS_API_KEY && !written.ELEVENLABS_API_KEY) missingAfterWrite.push('ELEVENLABS_API_KEY');
  if (env.ELEVENLABS_VOICE_ID && !written.ELEVENLABS_VOICE_ID) missingAfterWrite.push('ELEVENLABS_VOICE_ID');

  if (missingAfterWrite.length > 0) {
    s7.stop('warn', `Config saved but these keys were not written: ${missingAfterWrite.join(', ')}`);
    console.log();
    console.log(`  ${c.yellow}Add them manually to .env:${c.reset}`);
    for (const key of missingAfterWrite) {
      console.log(`  ${c.gray}echo "${key}=YOUR_VALUE" >> .env${c.reset}`);
    }
  } else {
    s7.stop('ok', `Configuration saved to .env (${Object.keys(written).filter(k => written[k]).length} keys)`);
  }

  // ── Step 8: launchd service (macOS) ──
  section('── Auto-start (macOS) ─────────────────────────');

  const plistDest = path.join(
    os.homedir(),
    'Library',
    'LaunchAgents',
    'com.claudeclaw.app.plist',
  );
  const plistInstalled = fs.existsSync(plistDest);

  if (plistInstalled) {
    console.log(
      `  ${c.green}✓${c.reset}  launchd service already installed`,
    );
    const reinstall = await ask('Reinstall?', 'N');
    if (reinstall.toLowerCase() === 'y') {
      installLaunchd(plistDest);
    }
  } else {
    const install = await ask(
      'Install as a background service that starts on login?',
      'Y',
    );
    if (install.toLowerCase() !== 'n') {
      installLaunchd(plistDest);
    } else {
      console.log(`  ${c.gray}Run manually: npm run dev${c.reset}`);
    }
  }

  // ── Step 9: Final summary ──
  console.log();
  console.log(
    `  ${c.cyan}╔══════════════════════════════════════════╗${c.reset}`,
  );
  console.log(
    `  ${c.cyan}║${c.reset}${c.bold}           ClaudeClaw is ready!           ${c.reset}${c.cyan}║${c.reset}`,
  );
  console.log(
    `  ${c.cyan}╚══════════════════════════════════════════╝${c.reset}`,
  );
  console.log();

  // Checklist
  console.log(
    `  ${c.green}✓${c.reset}  Bot token configured${botUsername ? ` (@${botUsername})` : ''}`,
  );

  if (env.ALLOWED_CHAT_ID) {
    console.log(
      `  ${c.green}✓${c.reset}  Chat ID locked to: ${env.ALLOWED_CHAT_ID}`,
    );
  } else {
    console.log(
      `  ${c.yellow}⚠${c.reset}  Chat ID: not set (bot will prompt on first message)`,
    );
  }

  if (env.GROQ_API_KEY) {
    console.log(`  ${c.green}✓${c.reset}  Voice STT: Groq Whisper`);
  } else {
    console.log(`  ${c.gray}-${c.reset}  Voice STT: not configured`);
  }

  if (env.ELEVENLABS_API_KEY && env.ELEVENLABS_VOICE_ID) {
    console.log(`  ${c.green}✓${c.reset}  Voice TTS: ElevenLabs`);
  } else {
    console.log(`  ${c.gray}-${c.reset}  Voice TTS: not configured`);
  }

  if (fs.existsSync(plistDest)) {
    console.log(`  ${c.green}✓${c.reset}  Service: installed (starts on login)`);
  } else {
    console.log(
      `  ${c.yellow}⚠${c.reset}  Service: run manually with npm run dev`,
    );
  }

  console.log();
  console.log(`  ${c.bold}Commands available in Telegram:${c.reset}`);
  console.log(`    /voice    toggle voice responses`);
  console.log(`    /memory   see what I remember about you`);
  console.log(`    /forget   clear session`);
  console.log(`    /newchat  fresh start`);
  console.log(`    /chatid   get your chat ID`);
  console.log();
  console.log(`  ${c.gray}Logs:  tail -f /tmp/claudeclaw.log${c.reset}`);
  console.log(
    `  ${c.gray}Start: npm run dev  (or npm start for prod build)${c.reset}`,
  );
  console.log();
}

function installLaunchd(dest: string) {
  const s = spinner('Installing launchd service...');
  try {
    const nodePath = process.execPath;
    const entryPoint = path.join(PROJECT_ROOT, 'dist', 'index.js');
    const pathEnv = process.env.PATH ?? '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin';

    // Generate plist dynamically so paths are correct for this machine
    const plistContent = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.claudeclaw.app</string>
  <key>ProgramArguments</key>
  <array>
    <string>${nodePath}</string>
    <string>${entryPoint}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>/tmp/claudeclaw.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/claudeclaw.err</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>NODE_ENV</key>
    <string>production</string>
    <key>PATH</key>
    <string>${pathEnv}</string>
    <key>HOME</key>
    <string>${os.homedir()}</string>
  </dict>
</dict>
</plist>`;

    const destDir = path.dirname(dest);
    fs.mkdirSync(destDir, { recursive: true });
    fs.writeFileSync(dest, plistContent, 'utf-8');
    execSync(`launchctl load "${dest}"`, { stdio: 'pipe' });
    s.stop('ok', 'Service installed. ClaudeClaw will start automatically on login.');
  } catch {
    s.stop('warn', `Manual install: run  launchctl load "${dest}"`);
  }
}

main()
  .catch((err) => {
    console.error(`\n  ${c.red}Setup failed:${c.reset}`, err);
    process.exit(1);
  })
  .finally(() => {
    rl.close();
  });
