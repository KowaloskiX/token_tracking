declare global {
  interface Window {
    google: any;
  }
}

export const initializeGoogleAuth = (
  clientId: string,
  callback: (response: any) => void
) => {
  if (typeof window === "undefined") return;

  window.google?.accounts.id.initialize({
    client_id: clientId,
    callback: callback,
    ux_mode: 'popup',
    cancel_on_tap_outside: true,
    prompt_parent_id: null,
    auto_select: false,
    itp_support: true,
    context: 'signin'
  });
};

export const renderGoogleButton = (buttonId: string) => {
  const getResponsiveWidth = () => {
    const windowWidth = window.innerWidth;
    if (windowWidth < 480) return 260; // Mobile devices
    if (windowWidth < 768) return 280; // Tablets
    return 300; // Desktop
  };

  window.google?.accounts.id.renderButton(
    document.getElementById(buttonId),
    {
      type: "standard",
      theme: "outline",
      size: "large",
      text: "signin_with",
      shape: "rectangular",
      locale: "pl_PL",
      width: getResponsiveWidth()
    }
  );

  // Add resize listener to update button width
  window.addEventListener('resize', () => {
    window.google?.accounts.id.renderButton(
      document.getElementById(buttonId),
      {
        type: "standard",
        theme: "outline",
        size: "large",
        text: "signin_with",
        shape: "rectangular",
        locale: "pl_PL",
        width: getResponsiveWidth()
      }
    );
  });
};

export const handleGoogleSignIn = async (response: any) => {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/users/auth/google`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        credential: response.credential,
      }),
    });

    if (!res.ok) throw new Error('Google authentication failed');
    
    return await res.json();
  } catch (error) {
    throw error;
  }
};