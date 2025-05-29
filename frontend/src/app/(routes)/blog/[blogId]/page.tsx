"use client"
import BlogSection from "@/components/landing/BlogSection";
import Footer from "@/components/landing/Footer";
import Navbar from "@/components/landing/Navbar";
import { blogs } from "@/app/constants/blogs";
import { useParams } from "next/navigation";
import { notFound } from "next/navigation";

const Blog = () => {
    const params = useParams();
    const blogId = params.blogId as string;
    
    const blog = blogs.find(b => b.id === blogId);
    
    if (!blog) {
        notFound();
    }

    return (
        <div>
            <Navbar />
            <BlogSection blog={blog} />
            <Footer />
        </div>
    )
}

export default Blog;