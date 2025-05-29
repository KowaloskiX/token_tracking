// Server URL configuration
const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

// Get all members in the user's organization
export async function getOrganizationMembers() {
    try {
        // Send a GET request to fetch all organization members
        const response = await fetch(`${serverUrl}/organizations/members`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`, // Include the user's token for authentication
            }
        });

        // Check if the response is not OK and handle errors
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Failed to retrieve organization members");
        }

        // Parse and return the list of members from the response
        const data = await response.json();
        return data.members;
    } catch (error) {
        // Log and rethrow the error for further handling
        console.error('Get organization members error:', error);
        throw error;
    }
}

// Update a team member's role
export async function updateMemberRole(memberId: string, role: string) {
    try {
        // Send a PATCH request to update the role of a specific member
        const response = await fetch(`${serverUrl}/organizations/members/${memberId}/role`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`, // Include the user's token for authentication
            },
            body: JSON.stringify({ role }) // Send the new role in the request body
        });

        // Check if the response is not OK and handle errors
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Failed to update member role");
        }

        // Parse and return the updated member data from the response
        return await response.json();
    } catch (error) {
        // Log and rethrow the error for further handling
        console.error('Update member role error:', error);
        throw error;
    }
}

// Remove a member from the organization
export async function removeMember(memberId: string) {
    try {
        // Send a DELETE request to remove a specific member from the organization
        const response = await fetch(`${serverUrl}/organizations/members/${memberId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`, // Include the user's token for authentication
            }
        });

        // Check if the response is not OK and handle errors
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Failed to remove member");
        }

        // Parse and return the response data (if any)
        return await response.json();
    } catch (error) {
        // Log and rethrow the error for further handling
        console.error('Remove member error:', error);
        throw error;
    }
}

// Leave the current organization
export async function leaveOrganization() {
    try {
        // Send a DELETE request to leave the organization
        const response = await fetch(`${serverUrl}/organizations/members/leave`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
            }
        });

        // Check if the response is not OK and handle errors
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Nie udało się opuścić organizacji");
        }

        // Parse and return the response data
        return await response.json();
    } catch (error) {
        // Log and rethrow the error for further handling
        console.error('Leave organization error:', error);
        throw error;
    }
}