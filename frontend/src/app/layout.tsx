import "./globals.css";
import Script from "next/script";
import type { Metadata, Viewport } from "next";
import { DashboardProvider } from "@/context/DashboardContext";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { satoshi } from "@/app/fonts/fonts";
import { Toaster } from "@/components/Toaster";

export const metadata: Metadata = {
  title: "Asystent AI",
  description: "Zwiększ efektywność w codziennej pracy z Asystentem AI.",
};

export const viewport: Viewport = {
  themeColor: "#F5EFE4",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <Script
          id="google-tag-manager"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
              new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
              j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
              'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
              })(window,document,'script','dataLayer','GTM-K4B65DPW');
            `,
          }}
        />
        <Script id="cookiebot-blocker" strategy="beforeInteractive">
          {`
            (function() {
              // Block Cookiebot initialization
              window.CookiebotCallback_OnLoad = function() {};
              window.CookiebotCallback_OnAccept = function() {};
              window.CookiebotCallback_OnDecline = function() {};
              
              // Add blocking style immediately
              var style = document.createElement('style');
              style.innerHTML = '#CookiebotWidget, .CookiebotWidget-logo, .CookiebotWidget-close, #CookiebotWidget-widgetContent { display: none !important; visibility: hidden !important; }';
              document.head.appendChild(style);
              
              // Block any potential script loading
              var originalCreateElement = document.createElement;
              document.createElement = function(tagName) {
                var element = originalCreateElement.call(document, tagName);
                if (tagName.toLowerCase() === 'script') {
                  var originalSetAttribute = element.setAttribute;
                  element.setAttribute = function(name, value) {
                    if (value && typeof value === 'string' && value.includes('cookiebot')) {
                      return element;
                    }
                    return originalSetAttribute.call(this, name, value);
                  };
                }
                return element;
              };
            })();
          `}
        </Script>
      </head>

      <body className={satoshi.variable}>
        <noscript
          dangerouslySetInnerHTML={{
            __html: `
            <iframe src="https://www.googletagmanager.com/ns.html?id=GTM-K4B65DPW"
            height="0" width="0" style="display:none;visibility:hidden"></iframe>
            `,
          }}
        />

        <SpeedInsights />
        <DashboardProvider>
          {children}
        </DashboardProvider>

        <Toaster />
      </body>
    </html>
  );
}
