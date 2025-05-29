import React from 'react';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbSeparator,
  BreadcrumbEllipsis,
} from "@/components/ui/breadcrumb";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface PathItem {
  id: string;
  name: string;
}

interface MemoryBreadcrumbProps {
  path: PathItem[];
  onNavigate: (newPath: PathItem[]) => void;
}

export const MemoryBreadcrumb: React.FC<MemoryBreadcrumbProps> = ({ path, onNavigate }) => {
  // Show ellipsis when path is more than 2 levels deep
  const showEllipsis = path.length > 2;
  
  // Get the visible items
  const getVisibleItems = () => {
    if (!showEllipsis) {
      return path;
    }
    return [path[0], path[path.length - 1]];
  };

  // Get the hidden items for the dropdown
  const getHiddenItems = () => {
    if (!showEllipsis) {
      return [];
    }
    return path.slice(1, -1);
  };

  const visibleItems = getVisibleItems();
  const hiddenItems = getHiddenItems();

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink 
            onClick={() => onNavigate([])}
            className="cursor-pointer"
          >
            Home
          </BreadcrumbLink>
        </BreadcrumbItem>

        {visibleItems.map((folder, index) => {
          const isFirstVisible = showEllipsis && index === 0;

          return (
            <React.Fragment key={folder.id}>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink 
                  onClick={() => {
                    const newPath = showEllipsis && index === 1 
                      ? path.slice(0, path.length) 
                      : path.slice(0, path.indexOf(folder) + 1);
                    onNavigate(newPath);
                  }}
                  className="cursor-pointer"
                >
                  {folder.name}
                </BreadcrumbLink>
              </BreadcrumbItem>

              {isFirstVisible && (
                <>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <DropdownMenu>
                      <DropdownMenuTrigger className="flex items-center gap-1">
                        <BreadcrumbEllipsis className="h-4 w-4" />
                        <span className="sr-only">Toggle menu</span>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        {hiddenItems.map((hiddenFolder) => (
                          <DropdownMenuItem 
                            key={hiddenFolder.id}
                            onClick={() => {
                              onNavigate(path.slice(0, path.indexOf(hiddenFolder) + 1));
                            }}
                          >
                            {hiddenFolder.name}
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </BreadcrumbItem>
                </>
              )}
            </React.Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
};