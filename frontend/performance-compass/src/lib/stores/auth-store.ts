import { create } from "zustand";
import { api, type User as BackendUser, type SystemRole, type UserPermissionProfile, type ModulePermission } from "../api";

/**
 * Auth Store
 * 
 * Manages JWT authentication state, current user info, and comprehensive permissions.
 * Syncs with backend on login/register and restores session on page load.
 */

export interface UserModule {
  module_key: string;
  access_level: "full" | "read" | "none";
}

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  system_role: SystemRole;
  org_id: string;
  designation?: string;
  department?: string;
  /** Accent for avatar chip (from API `avatar_color`). */
  avatarColor?: string;
  permissions?: UserPermissionProfile;
}

interface AuthState {
  // Auth state
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Permissions
  permissions: UserPermissionProfile | null;
  modules: ModulePermission[];

  // Permission checking methods
  hasModule: (key: string) => boolean;
  canView: (moduleKey: string) => boolean;
  canCreate: (moduleKey: string) => boolean;
  canEdit: (moduleKey: string) => boolean;
  canApprove: (moduleKey: string) => boolean;
  canDelete: (moduleKey: string) => boolean;
  hasCapability: (capability: keyof UserPermissionProfile) => boolean;

  // Auth actions
  login: (email: string, password: string) => Promise<void>;
  register: (
    company_name: string,
    admin_name: string,
    admin_email: string,
    password: string,
    domain?: string,
    org_size?: string
  ) => Promise<void>;
  logout: () => void;
  restoreSession: () => Promise<void>;
  loadPermissions: () => Promise<void>;
  getToken: () => string | null;
  clearError: () => void;
}

// Helper to map backend user to UI user
function mapBackendUser(backendUser: BackendUser): AuthUser {
  return {
    id: backendUser.id,
    name: backendUser.name,
    email: backendUser.email,
    system_role: backendUser.system_role,
    org_id: backendUser.org_id,
    permissions: backendUser.permissions,
    avatarColor: backendUser.avatar_color ?? "#6366f1",
  };
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // Initial state
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  permissions: null,
  modules: [],

  // ========== Permission Checking Methods ==========

  // Check if user has access to a module (backward compatibility)
  hasModule: (key: string) => {
    const { modules } = get();
    return modules.some((m) => m.module_key === key && m.can_view);
  },

  // Check view permission on module
  canView: (moduleKey: string) => {
    const { modules } = get();
    return modules.some((m) => m.module_key === moduleKey && m.can_view);
  },

  // Check create permission on module
  canCreate: (moduleKey: string) => {
    const { modules } = get();
    return modules.some((m) => m.module_key === moduleKey && m.can_create);
  },

  // Check edit permission on module
  canEdit: (moduleKey: string) => {
    const { modules } = get();
    return modules.some((m) => m.module_key === moduleKey && m.can_edit);
  },

  // Check approve permission on module
  canApprove: (moduleKey: string) => {
    const { modules } = get();
    return modules.some((m) => m.module_key === moduleKey && m.can_approve);
  },

  // Check delete permission on module
  canDelete: (moduleKey: string) => {
    const { modules } = get();
    return modules.some((m) => m.module_key === moduleKey && m.can_delete);
  },

  // Check user capability (e.g., can_create_plants, can_invite_employees)
  hasCapability: (capability: keyof UserPermissionProfile) => {
    const { permissions } = get();
    if (!permissions) return false;
    const value = permissions[capability];
    return typeof value === "boolean" ? value : false;
  },

  // ========== Auth Actions ==========

  // Login with email and password
  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.login({ email, password });
      api.setToken(response.access_token);

      set({
        user: mapBackendUser(response.user),
        isAuthenticated: true,
        isLoading: false,
      });

      // Load permissions
      await get().loadPermissions();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Login failed";
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  // Register new organization and admin user
  register: async (
    company_name: string,
    admin_name: string,
    admin_email: string,
    password: string,
    domain?: string,
    org_size?: string
  ) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.register({
        company_name,
        admin_name,
        admin_email,
        password,
        domain,
        org_size,
      });

      api.setToken(response.access_token);

      set({
        user: mapBackendUser(response.user),
        isAuthenticated: true,
        isLoading: false,
      });

      // Load permissions
      await get().loadPermissions();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Registration failed";
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  // Logout and clear session
  logout: () => {
    api.clearToken();
    set({
      user: null,
      isAuthenticated: false,
      permissions: null,
      modules: [],
      error: null,
    });
  },

  // Restore session from stored token (called on app load)
  restoreSession: async () => {
    set({ isLoading: true });
    try {
      // Try to fetch current user if token exists
      const user = await api.getMe();
      set({
        user: mapBackendUser(user),
        isAuthenticated: true,
        isLoading: false,
      });

      // Load permissions
      await get().loadPermissions();
    } catch {
      // Token invalid or expired
      api.clearToken();
      set({
        user: null,
        isAuthenticated: false,
        permissions: null,
        modules: [],
        isLoading: false,
      });
    }
  },

  // Load comprehensive permission profile for current user
  loadPermissions: async () => {
    try {
      const profile = await api.getMyPermissions();
      set({ 
        permissions: profile,
        modules: profile.modules || [],
      });
    } catch (error) {
      console.error("Failed to load permissions:", error);
      // Continue without throwing - permissions will be empty but auth continues
    }
  },

  // Get current auth token
  getToken: () => {
    return api.getToken();
  },

  // Clear error message
  clearError: () => set({ error: null }),
}));
