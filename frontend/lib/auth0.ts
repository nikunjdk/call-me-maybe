import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { authDisabled } from "./authDisabled";

export { authDisabled };

export const auth0: Auth0Client | null = authDisabled()
  ? null
  : new Auth0Client({
      signInReturnToPath: "/",
    });
