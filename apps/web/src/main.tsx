import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ClerkProvider, Show, SignIn, SignUp } from "@clerk/react";
import { publishableKeyFromHost } from "@clerk/react/internal";
import { dark } from "@clerk/themes";
import { Link, Route, Router as WouterRouter, Switch, useLocation } from "wouter";
import { App } from "./App";
import "./styles.css";

const clerkPubKey = publishableKeyFromHost(
  window.location.hostname,
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY,
);
const clerkProxyUrl = import.meta.env.VITE_CLERK_PROXY_URL;
const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");
function stripBase(path: string): string {
  return basePath && path.startsWith(basePath) ? path.slice(basePath.length) || "/" : path;
}
const appearance = {
  theme: dark,
  options: {
    logoPlacement: "inside" as const,
    logoLinkUrl: basePath || "/",
    logoImageUrl: `${window.location.origin}${basePath}/logo.svg`,
  },
  variables: {
    colorPrimary: "#d4b86a",
    colorForeground: "#e9e1d0",
    colorMutedForeground: "#9ba29b",
    colorBackground: "#171d1b",
    colorInput: "#0e1211",
    colorInputForeground: "#e9e1d0",
    colorDanger: "#e98b79",
    colorNeutral: "#4a5750",
    fontFamily: '"DM Sans", ui-sans-serif, system-ui, sans-serif',
    borderRadius: "6px",
  },
};

function Landing() {
  return <main className="auth-landing"><img src={`${basePath}/logo.svg`} alt="" /><p className="eyebrow">Professional non-destructive color workflow</p><h1>Film Look Studio</h1><p>Build, verify, save, and package camera-ready film Looks in your private workspace.</p><div className="button-row"><Link className="primary" href="/sign-up">Create account</Link><Link className="secondary" href="/sign-in">Sign in</Link></div></main>;
}
function Home() {
  return <><Show when="signed-in"><App /></Show><Show when="signed-out"><Landing /></Show></>;
}
function AuthPage({ mode }: { mode: "in" | "up" }) {
  return <main className="auth-page">{mode === "in"
    ? <SignIn routing="path" path={`${basePath}/sign-in`} signUpUrl={`${basePath}/sign-up`} />
    : <SignUp routing="path" path={`${basePath}/sign-up`} signInUrl={`${basePath}/sign-in`} />}</main>;
}
function Routes() {
  const [, setLocation] = useLocation();
  return <ClerkProvider
    publishableKey={clerkPubKey}
    proxyUrl={clerkProxyUrl}
    appearance={appearance}
    signInUrl={`${basePath}/sign-in`}
    signUpUrl={`${basePath}/sign-up`}
    localization={{ signIn: { start: { title: "Welcome back", subtitle: "Open your Film Look workspace" } }, signUp: { start: { title: "Create your studio account", subtitle: "Save private workspaces and Looks" } } }}
    routerPush={(to) => setLocation(stripBase(to))}
    routerReplace={(to) => setLocation(stripBase(to), { replace: true })}
  ><Switch><Route path="/" component={Home} /><Route path="/sign-in/*?"><AuthPage mode="in" /></Route><Route path="/sign-up/*?"><AuthPage mode="up" /></Route></Switch></ClerkProvider>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><WouterRouter base={basePath}><Routes /></WouterRouter></StrictMode>);