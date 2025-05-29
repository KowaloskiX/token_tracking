import { Check, CheckCircle, Info } from "lucide-react";
import Image from "next/image";
import { Blog } from "@/app/constants/blogs";

interface BlogSectionProps {
  blog: Blog;
}

export default function BlogSection({ blog }: BlogSectionProps) {
  const renderBlock = (block: any, index: number) => {
    switch (block.type) {
      case 'section':
        return (
          <div key={index}>
            <h2 className="mt-16 text-pretty text-2xl sm:text-3xl tracking-tight text-foreground">
              {block.content.title}
            </h2>
            <p className="mt-6 text-justify text-sm sm:text-base">{block.content.text}</p>
          </div>
        );
      
      case 'image':
        return (
          <div key={index} className="my-16">
            <Image
              width={2000}
              height={1200}
              alt={block.content.image?.alt || ""}
              src={block.content.image?.src || ""}
              className="aspect-video rounded-lg bg-gray-50 object-cover"
            />
            {block.content.image?.caption && (
              <p className="mt-2 text-sm text-gray-500 text-center">
                {block.content.image.caption}
              </p>
            )}
          </div>
        );

      case 'mainPoints':
        return (
          <ul key={index} role="list" className="mt-8 max-w-xl space-y-8 text-body-text">
            {blog.content.mainPoints.map((point, idx) => (
              <li key={idx} className="flex gap-x-3">
                <CheckCircle aria-hidden="true" className="mt-1 size-5 flex-none text-foreground" />
                <span>
                  <strong className="text-foreground">{point.title}.</strong> {point.description}
                </span>
              </li>
            ))}
          </ul>
        );

      default:
        return null;
    }
  };

  return (
    <div className="sm:px-6 py-20 sm:py-32 lg:px-8 text-body-text">
      <div className="mx-auto sm:shadow p-6 sm:p-12 sm:pb-28 rounded-xl border-secondary-border sm:border-2 max-w-4xl text-base/7 text-gray-700">
        <Image
          width={2000}
          height={1200}
          alt=""
          src={blog.image}
          className="aspect-video rounded-lg bg-gray-50 object-cover"
        />
        <p className="text-base/7 text-foreground mt-12 font-medium">{blog.subtitle}</p>
        <h1 className="mt-2 text-pretty text-2xl sm:text-4xl tracking-tight text-foreground">
          {blog.title}
        </h1>
        <p className="mt-6 text-base sm:text-xl/8">{blog.description}</p>
        
        <div className="mt-10 w-full">
          {blog.content.blocks.map((block, index) => renderBlock(block, index))}

          {blog.quote && (
            <figure className="mt-10 border-l border-foreground pl-9">
              <blockquote className="text-foreground">
                <p>{blog.quote.text}</p>
              </blockquote>
              <figcaption className="mt-6 flex gap-x-4">
                <img
                  alt=""
                  src={blog.author.avatar}
                  className="size-6 flex-none rounded-full bg-gray-50"
                />
                <div className="text-sm/6">
                  <strong className="text-foreground">
                    {blog.quote.author}
                  </strong> – {blog.quote.role}
                </div>
              </figcaption>
            </figure>
          )}
        </div>
      </div>
    </div>
  );
}
