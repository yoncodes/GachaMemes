declare function parseInt(s: string, radix?: number): number;

interface Array<T> {
  map<U>(callback: (value: T, index: number, arr: T[]) => U, thisArg?: any): U[];
  find(predicate: (value: T, index: number, arr: T[]) => boolean, thisArg?: any): T | undefined;
  join(separator?: string): string;
}

interface String {
  split(separator: string | RegExp, limit?: number): string[];
  includes(searchString: string, position?: number): boolean;
}

interface Error {
  name: string;
  message: string;
  stack?: string;
}
declare var Error: {
  new (message?: string): Error;
  (message?: string): Error;
  prototype: Error;
};
