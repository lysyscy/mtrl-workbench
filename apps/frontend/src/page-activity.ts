import { createContext } from 'react';

// Retained pages keep drafts mounted; hidden grids must pause sizing work.
export const PageActivity = createContext(true);
