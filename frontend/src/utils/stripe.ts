export const createCheckoutSession = async (
  priceId: string, 
  interval: 'monthly' | 'annually',
  successUrl: string,
  cancelUrl: string
) => {
  try {
    const token = localStorage.getItem('token');
    if (!token) {
      throw new Error('No authentication token found');
    }

    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/stripe/create-checkout-session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ 
        price_id: priceId,
        interval,
        success_url: successUrl,
        cancel_url: cancelUrl
      }),
      credentials: 'include',
    });
    
    if (!response.ok) {
      const error = await response.json();
      console.error('Error response:', error);
      throw new Error(error.detail || 'Failed to create checkout session');
    }

    const data = await response.json();

    // 3. Redirect to Stripe Checkout
    if (data.url) {
      window.location.href = data.url;
    } else {
      throw new Error('No checkout URL received from server');
    }
  } catch (error) {
    console.error('Detailed error:', error);
    throw error;
  }
};