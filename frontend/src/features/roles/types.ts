// Types for the roles feature (mirror its backend schemas).

/**
 * A node in the screen tree. Top-level nodes (parent_screen_id = null) are
 * pages. A page can have child nodes ("features", e.g. the five analytics
 * widgets on the dashboard). Permissions are stored on the leaves: a page
 * with features is controlled through them; a page without features is its
 * own leaf.
 */
export type Screen = {
  id: number;
  parent_screen_id: number | null;
  /** Stable code identifier, e.g. "users" or "dashboard.recent_activity". */
  screen_key: string;
  name: string;
  /** Route for pages; null for features. */
  path: string | null;
  description: string | null;
};

export type RoleScreenAccess = { screen_id: number; can_read: boolean; can_write: boolean };

export type RoleSummary = {
  id: number;
  name: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
  /** A page this role can open; where its users land after login. */
  default_screen_id: number | null;
  user_count: number;
};

export type RoleDetail = RoleSummary & {
  /** One entry per leaf screen. */
  access: RoleScreenAccess[];
};
