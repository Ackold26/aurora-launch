// See https://kit.svelte.dev/docs/types#app

declare global {
  namespace App {
    interface Error {
      kind?: string;
      message: string;
    }
    interface Locals {}
    interface PageData {}
    interface PageState {}
    interface Platform {}
  }
}

export {};
