// Auth is handled entirely via httpOnly cookies (set by the backend).
// No client-side token storage or header injection needed.
// The `credentials: "include"` option on fetch sends cookies automatically.
