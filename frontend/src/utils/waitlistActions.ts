const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

export interface WaitlistResponse {
	status: string;
	message: string;
}

export interface WaitlistCountResponse {
	count: number;
}

export const submitToWaitlist = async (
	email: string
): Promise<WaitlistResponse> => {
	const response = await fetch(`${serverUrl}/waitlist/`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
		},
		body: JSON.stringify({ email }),
	});

	if (!response.ok) {
		const error = await response.json();
		throw new Error(error.detail || "Failed to submit to waitlist");
	}

	return response.json();
};

export const getWaitlistCount = async (): Promise<number> => {
	try {
		const response = await fetch(`${serverUrl}/waitlist/count`);
		if (!response.ok) {
			throw new Error("Failed to fetch waitlist count");
		}
		const data: WaitlistCountResponse = await response.json();
		return data.count;
	} catch (error) {
		console.error("Error fetching waitlist count:", error);
		return 0;
	}
};
