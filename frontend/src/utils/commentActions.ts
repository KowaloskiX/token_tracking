import { Comment } from "@/types/comments";
import { handleResponse } from "./api";

const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

// Function to get authorization headers for API requests
export function getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem("token"); // Retrieve the token from local storage
    return {
        "Content-Type": "application/json", // Specify JSON content type
        Authorization: `Bearer ${token || ""}`, // Include the token in the Authorization header
    };
}

// Function to fetch comments for a specific tender
export async function getComments(tenderId: string): Promise<Comment[]> {
    // Note the trailing slash after 'comments'
    const response = await fetch(`${serverUrl}/comments/?tender_id=${tenderId}`, {
        headers: getAuthHeaders(), // Include authorization headers
    });
    return handleResponse(response); // Handle and parse the response
}

// Function to create a new comment for a specific tender
export async function createComment(tenderId: string, text: string): Promise<Comment> {
    // Note the trailing slash after 'comments'
    const response = await fetch(`${serverUrl}/comments/`, {
        method: "POST", // HTTP method for creating a resource
        headers: getAuthHeaders(), // Include authorization headers
        body: JSON.stringify({ tender_id: tenderId, text }), // Send the tender ID and comment text in the request body
    });
    return handleResponse(response); // Handle and parse the response
}

// Function to update an existing comment
export async function updateComment(commentId: string, text: string): Promise<Comment> {
    // Note the trailing slash after 'comments'
    const response = await fetch(`${serverUrl}/comments/${commentId}`, {
        method: "PUT", // HTTP method for updating a resource
        headers: getAuthHeaders(), // Include authorization headers
        body: JSON.stringify({ text }), // Send the updated comment text in the request body
    });
    return handleResponse(response); // Handle and parse the response
}

// Function to delete a comment by its ID
export async function deleteComment(commentId: string): Promise<{ message: string }> {
    const response = await fetch(`${serverUrl}/comments/${commentId}`, { // removed trailing slash
        method: "DELETE", // HTTP method for deleting a resource
        headers: getAuthHeaders(), // Include authorization headers
    });
    return handleResponse(response); // Handle and parse the response
}