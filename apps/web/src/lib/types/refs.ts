// Avoid React's deprecated ref typing by using our own minimal shape.
export type MutableRef<T> = { current: T };
