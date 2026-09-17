export interface AuthenticateResponse {
  message?: string;
  error?: string;
}

export interface GitHubAccessTokenResponse {
  access_token: string;
}

export interface SignInOrganization {
  id: string;
  slug: string;
  name: string;
  logo?: string | null;
}

export interface SignInOptions {
  /** Social provider ids the organization has enabled */
  providers: string[];
  /** Whether email+password sign-in is offered */
  passwordEnabled: boolean;
  /** Whether the organization only admits invited members (no self sign-up) */
  inviteOnly: boolean;
  /** The organization scoping this screen, or null for a deployment-wide one */
  organization: SignInOrganization | null;
}
