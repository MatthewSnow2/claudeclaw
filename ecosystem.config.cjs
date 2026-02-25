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
  ],
};
