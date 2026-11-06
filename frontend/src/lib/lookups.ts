import { api } from "@/lib/api";
import type { LookupItem } from "@/lib/types";
import { useDebounced, useResource } from "@/lib/use-resource";

/**
 * Minimal id + label lists for dropdowns on pages that do not own the data
 * (see AGENTS.md "Lookups"). Always use this instead of the management
 * endpoint, so a page works even when the user has no access to the source page.
 *
 *   const { data: roles } = useLookup("roles");
 *   const { data: people } = useLookup("employees", search);   // server-side search
 */
export function useLookup(entity: string, search = "") {
  const q = useDebounced(search, 250);
  return useResource(() => api.get<LookupItem[]>(`/lookups/${entity}`, { q: q || undefined, limit: 50 }), [entity, q]);
}
