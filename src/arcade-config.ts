/**
 * Arcade MCP Gateway configuration.
 *
 * Provides Linear, GitHub, and Slack tools to Claude Code via the Arcade
 * MCP Gateway. Uses stdio transport (mcp-remote) because the SDK only
 * propagates stdio MCP servers to subagents.
 *
 * Keys come from ~/.env.shared (already authorized via yce-harness).
 */

import { readEnvFile } from './env.js';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const ARCADE_MCP_BASE_URL = 'https://api.arcade.dev/mcp';

const ARCADE_KEYS = ['ARCADE_API_KEY', 'ARCADE_GATEWAY_SLUG', 'ARCADE_USER_ID'] as const;

function loadArcadeEnv(): Record<string, string> {
  return readEnvFile([...ARCADE_KEYS]);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Returns true if all required Arcade keys are present.
 * Never throws — safe to call at startup.
 */
export function isArcadeConfigured(): boolean {
  const env = loadArcadeEnv();
  return !!(env.ARCADE_API_KEY && env.ARCADE_GATEWAY_SLUG);
}

/**
 * Build the stdio MCP server config for the Arcade gateway.
 * Uses `npx mcp-remote` to bridge HTTP -> stdio.
 */
export function getArcadeMcpConfig(): {
  command: string;
  args: string[];
} {
  const env = loadArcadeEnv();
  const apiKey = env.ARCADE_API_KEY;
  const slug = env.ARCADE_GATEWAY_SLUG;
  const userId = env.ARCADE_USER_ID || 'agent@local';

  if (!apiKey || !slug) {
    throw new Error('Arcade MCP not configured: missing ARCADE_API_KEY or ARCADE_GATEWAY_SLUG');
  }

  const gatewayUrl = `${ARCADE_MCP_BASE_URL}/${slug}`;

  return {
    command: 'npx',
    args: [
      '-y',
      'mcp-remote',
      gatewayUrl,
      '--header',
      `Authorization:Bearer ${apiKey}`,
      '--header',
      `Arcade-User-ID:${userId}`,
    ],
  };
}

// ---------------------------------------------------------------------------
// Tool name constants (for reference / future filtering)
// ---------------------------------------------------------------------------

export const ARCADE_LINEAR_TOOLS = [
  'mcp__arcade__Linear_WhoAmI',
  'mcp__arcade__Linear_GetNotifications',
  'mcp__arcade__Linear_GetRecentActivity',
  'mcp__arcade__Linear_GetTeam',
  'mcp__arcade__Linear_ListTeams',
  'mcp__arcade__Linear_ListIssues',
  'mcp__arcade__Linear_GetIssue',
  'mcp__arcade__Linear_CreateIssue',
  'mcp__arcade__Linear_UpdateIssue',
  'mcp__arcade__Linear_ArchiveIssue',
  'mcp__arcade__Linear_TransitionIssueState',
  'mcp__arcade__Linear_CreateIssueRelation',
  'mcp__arcade__Linear_ManageIssueSubscription',
  'mcp__arcade__Linear_ListComments',
  'mcp__arcade__Linear_AddComment',
  'mcp__arcade__Linear_UpdateComment',
  'mcp__arcade__Linear_ReplyToComment',
  'mcp__arcade__Linear_ListProjects',
  'mcp__arcade__Linear_GetProject',
  'mcp__arcade__Linear_GetProjectDescription',
  'mcp__arcade__Linear_CreateProject',
  'mcp__arcade__Linear_UpdateProject',
  'mcp__arcade__Linear_ArchiveProject',
  'mcp__arcade__Linear_CreateProjectUpdate',
  'mcp__arcade__Linear_ListProjectComments',
  'mcp__arcade__Linear_AddProjectComment',
  'mcp__arcade__Linear_ReplyToProjectComment',
  'mcp__arcade__Linear_ListInitiatives',
  'mcp__arcade__Linear_GetInitiative',
  'mcp__arcade__Linear_GetInitiativeDescription',
  'mcp__arcade__Linear_CreateInitiative',
  'mcp__arcade__Linear_UpdateInitiative',
  'mcp__arcade__Linear_ArchiveInitiative',
  'mcp__arcade__Linear_AddProjectToInitiative',
  'mcp__arcade__Linear_ListCycles',
  'mcp__arcade__Linear_GetCycle',
  'mcp__arcade__Linear_ListLabels',
  'mcp__arcade__Linear_ListWorkflowStates',
  'mcp__arcade__Linear_LinkGithubToIssue',
] as const;

export const ARCADE_GITHUB_TOOLS = [
  'mcp__arcade__Github_WhoAmI',
  'mcp__arcade__Github_GetUserRecentActivity',
  'mcp__arcade__Github_GetUserOpenItems',
  'mcp__arcade__Github_GetReviewWorkload',
  'mcp__arcade__Github_GetNotificationSummary',
  'mcp__arcade__Github_ListNotifications',
  'mcp__arcade__Github_GetRepository',
  'mcp__arcade__Github_SearchMyRepos',
  'mcp__arcade__Github_ListOrgRepositories',
  'mcp__arcade__Github_ListRepositoryCollaborators',
  'mcp__arcade__Github_ListRepositoryActivities',
  'mcp__arcade__Github_CountStargazers',
  'mcp__arcade__Github_ListStargazers',
  'mcp__arcade__Github_SetStarred',
  'mcp__arcade__Github_CreateBranch',
  'mcp__arcade__Github_GetFileContents',
  'mcp__arcade__Github_CreateOrUpdateFile',
  'mcp__arcade__Github_UpdateFileLines',
  'mcp__arcade__Github_ListIssues',
  'mcp__arcade__Github_GetIssue',
  'mcp__arcade__Github_CreateIssue',
  'mcp__arcade__Github_UpdateIssue',
  'mcp__arcade__Github_CreateIssueComment',
  'mcp__arcade__Github_ListPullRequests',
  'mcp__arcade__Github_GetPullRequest',
  'mcp__arcade__Github_CreatePullRequest',
  'mcp__arcade__Github_UpdatePullRequest',
  'mcp__arcade__Github_MergePullRequest',
  'mcp__arcade__Github_ManagePullRequest',
  'mcp__arcade__Github_CheckPullRequestMergeStatus',
  'mcp__arcade__Github_ListPullRequestCommits',
  'mcp__arcade__Github_AssignPullRequestUser',
  'mcp__arcade__Github_ManagePullRequestReviewers',
  'mcp__arcade__Github_SubmitPullRequestReview',
  'mcp__arcade__Github_CreateReviewComment',
  'mcp__arcade__Github_CreateReplyForReviewComment',
  'mcp__arcade__Github_ListReviewCommentsOnPullRequest',
  'mcp__arcade__Github_ListReviewCommentsInARepository',
  'mcp__arcade__Github_ResolveReviewThread',
  'mcp__arcade__Github_ListRepositoryLabels',
  'mcp__arcade__Github_ManageLabels',
  'mcp__arcade__Github_ListProjects',
  'mcp__arcade__Github_ListProjectFields',
  'mcp__arcade__Github_ListProjectItems',
  'mcp__arcade__Github_SearchProjectItem',
  'mcp__arcade__Github_UpdateProjectItem',
] as const;

export const ARCADE_SLACK_TOOLS = [
  'mcp__arcade__Slack_WhoAmI',
  'mcp__arcade__Slack_GetUsersInfo',
  'mcp__arcade__Slack_ListUsers',
  'mcp__arcade__Slack_ListConversations',
  'mcp__arcade__Slack_GetConversationMetadata',
  'mcp__arcade__Slack_GetUsersInConversation',
  'mcp__arcade__Slack_GetMessages',
  'mcp__arcade__Slack_SendMessage',
] as const;
