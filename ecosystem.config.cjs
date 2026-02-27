module.exports = {
  apps: [
    {
      name: 'ea-claude',
      script: 'dist/index.js',
      cwd: __dirname,
      interpreter: 'node',
      env: {
        NODE_ENV: 'production',
      },
      // Prevent rapid crash loops: wait 5s between restarts
      restart_delay: 5000,
      // Stop retrying after 10 consecutive failures
      max_restarts: 10,
      // Reset restart counter after 60s of stable uptime
      min_uptime: 60000,
      // Exponential backoff on repeated crashes
      exp_backoff_restart_delay: 1000,
    },

    // Dispatch workers - each runs its own Claude agent subprocess
    // MAX_CONCURRENT_AGENTS=1 per process, so concurrency scales by process count
    {
      name: 'ea-claude-default',
      script: 'dist/worker.js',
      args: '--type default',
      cwd: __dirname,
      interpreter: 'node',
      env: {
        NODE_ENV: 'production',
      },
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: 60000,
      exp_backoff_restart_delay: 1000,
    },
    {
      name: 'ea-claude-starscream',
      script: 'dist/worker.js',
      args: '--type starscream',
      cwd: __dirname,
      interpreter: 'node',
      env: {
        NODE_ENV: 'production',
      },
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: 60000,
      exp_backoff_restart_delay: 1000,
    },
    {
      name: 'ea-claude-ravage',
      script: 'dist/worker.js',
      args: '--type ravage',
      cwd: __dirname,
      interpreter: 'node',
      env: {
        NODE_ENV: 'production',
      },
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: 60000,
      exp_backoff_restart_delay: 1000,
    },
    {
      name: 'ea-claude-soundwave',
      script: 'dist/worker.js',
      args: '--type soundwave',
      cwd: __dirname,
      interpreter: 'node',
      env: {
        NODE_ENV: 'production',
      },
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: 60000,
      exp_backoff_restart_delay: 1000,
    },
    {
      name: 'ea-claude-astrotrain',
      script: 'dist/worker.js',
      args: '--type astrotrain',
      cwd: __dirname,
      interpreter: 'node',
      env: {
        NODE_ENV: 'production',
      },
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: 60000,
      exp_backoff_restart_delay: 1000,
    },
  ],
};
