export interface Comment {
    _id: string;
    tender_id: string;
    user_id: string;
    org_id: string;
    text: string;
    created_at: string;
    updated_at?: string;
    user_info?: {
        name: string;
        avatar_img?: string;
        [key: string]: any;
    };
}