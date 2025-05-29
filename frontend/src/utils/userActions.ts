import { LoginCredentials, RegisterResponse, User, UserCreateData } from "@/types";

const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

  
  export async function loginUser(credentials: LoginCredentials) {
    try {
      const response = await fetch(`${serverUrl}/users/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });
  

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
      }
  
      const data = await response.json();
      return {
        user: data.user,
        token: data.access_token,
      };
    } catch (error) {
      throw error;
    }
  }


  export async function registerUser(userData: UserCreateData): Promise<RegisterResponse> {
    try {
      // Ensure org_id and role are included with default values
      const dataToSend = {
        ...userData,
        org_id: userData.org_id || "",  // Default empty string matches Python Optional[str]
        role: userData.role || "member"         // Default value matches Python default
      };
  

      const response = await fetch(`${serverUrl}/users/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(dataToSend),
      });
  
      if (!response.ok) {
        const errorData = await response.json();
        console.error('Registration response error:', {
          status: response.status,
          statusText: response.statusText,
          error: errorData
        });
        throw new Error(errorData.detail || 'Registration failed');
      }
  
      const data: RegisterResponse = await response.json();
      return data;
    } catch (error) {
      console.error('Registration error:', error);
      throw error;
    }
  }

export async function updateUserProfile(userId: string, userData: Partial<User>) {
  try {
    const response = await fetch(`${serverUrl}/users/${userId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update profile');
    }

    const updatedUser = await response.json();
    return updatedUser;
  } catch (error) {
    console.error('Update profile error:', error);
    throw error;
  }
}

export const getUserStats = async (userId: string) => {
  try {
    const response = await fetch(`${serverUrl}/users/${userId}/stats`);
    if (!response.ok) throw new Error('Failed to fetch user stats');
    return await response.json();
  } catch (error) {
    throw error;
  }
};

export async function deleteUserAccount(userId: string) {
  try {
    const response = await fetch(`${serverUrl}/users/${userId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete account');
    }

    return await response.json();
  } catch (error) {
    console.error('Delete account error:', error);
    throw error;
  }
}

// Update the function to accept the name parameter
export async function acceptInvitation(token: string, email: string, password: string, name: string) {
  const response = await fetch(`${serverUrl}/invitations/accept`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ token, email, password, name })
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to accept invitation");
  }

  const data = await response.json();
  return data;
}

interface MarketingConsent {
  communication_emails?: boolean;
  marketing_emails?: boolean;
  social_emails?: boolean;
  security_emails: boolean;
}

export async function updateMarketingConsent(userId: string, consentData: MarketingConsent) {
  try {
    const response = await fetch(`${serverUrl}/users/${userId}/consent`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify(consentData),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update consent settings');
    }

    return await response.json();
  } catch (error) {
    console.error('Update consent error:', error);
    throw error;
  }
}

// Function to create an invitation for a user with a specified email and role
// Default role is set to "member" if not provided
export async function createInvitation(email: string, role: string = "member") {
  try {
    // Send a POST request to the server to create an invitation
    const response = await fetch(`${serverUrl}/invitations/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json', // Specify JSON content type
        'Authorization': `Bearer ${localStorage.getItem('token')}`, // Include authorization token
      },
      body: JSON.stringify({ email, role }), // Send email and role in the request body
    });

    // Check if the response is not OK (status code outside 200-299 range)
    if (!response.ok) {
      const errorData = await response.json(); // Parse error details from the response
      throw new Error(errorData.detail || "Nie udało się wysłać zaproszenia"); // Throw an error with details
    }

    // Parse and return the response data if the request was successful
    const data = await response.json();
    return data;
  } catch (error) {
    // Log the error to the console for debugging
    console.error('Create invitation error:', error);
    throw error; // Re-throw the error to be handled by the caller
  }
}

export async function getInvitationByToken(token: string) {
  try {
    const response = await fetch(`${serverUrl}/invitations/by-token/${token}`);
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "Nie udało się pobrać szczegółów zaproszenia");
    }
    
    return await response.json();
  } catch (error) {
    console.error('Get invitation details error:', error);
    throw error;
  }
}

// Function to request a password reset email
// Sends a POST request to the server with the user's email to initiate the password reset process
export async function requestPasswordReset(email: string): Promise<void> {
  try {
    const response = await fetch(`${serverUrl}/forgot-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json', // Specify JSON content type
      },
      body: JSON.stringify({ email }), // Include the email in the request body
    });

    // Check if the response is not OK (status code outside 200-299 range)
    if (!response.ok) {
      const error = await response.json(); // Parse error details from the response
      throw new Error(error.detail || 'Failed to request password reset'); // Throw an error with details
    }
    
    // Parse and return the response data if the request was successful
    return await response.json();
  } catch (error) {
    // Log the error to the console for debugging
    console.error('Password reset request error:', error);
    throw error; // Re-throw the error to be handled by the caller
  }
}

// Function to reset password using token
// Sends a POST request to the server with the reset token and new password to complete the password reset process
export async function resetPassword(token: string, password: string): Promise<void> {
  try {
    const response = await fetch(`${serverUrl}/reset-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json', // Specify JSON content type
      },
      body: JSON.stringify({ token, password }), // Include the token and new password in the request body
    });

    // Check if the response is not OK (status code outside 200-299 range)
    if (!response.ok) {
      const error = await response.json(); // Parse error details from the response
      throw new Error(error.detail || 'Failed to reset password'); // Throw an error with details
    }
    
    // Parse and return the response data if the request was successful
    return await response.json();
  } catch (error) {
    // Log the error to the console for debugging
    console.error('Password reset error:', error);
    throw error; // Re-throw the error to be handled by the caller
  }
}

// Function to change the user's password
// Sends a POST request to the server with the current and new passwords
export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  try {
    // Make a POST request to the change-password endpoint
    const response = await fetch(`${serverUrl}/users/change-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json', // Specify JSON content type
        'Authorization': `Bearer ${localStorage.getItem('token')}`, // Include authorization token
      },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }), // Send current and new passwords in the request body
    });

    // Check if the response is not OK (status code outside 200-299 range)
    if (!response.ok) {
      const error = await response.json(); // Parse error details from the response
      throw new Error(error.detail || 'Failed to change password'); // Throw an error with details
    }
    
    // Parse and return the response data if the request was successful
    return await response.json();
  } catch (error) {
    // Log the error to the console for debugging
    console.error('Change password error:', error);
    throw error; // Re-throw the error to be handled by the caller
  }
}