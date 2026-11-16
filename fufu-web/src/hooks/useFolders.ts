import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { folderApi, type Folder, type FolderArticles } from '../api/folders';
import { unwrapOr } from '../api/unwrap';

/** 获取所有文件夹列表 */
export function useFolders() {
  return useQuery({
    queryKey: ['folders'],
    queryFn: async () => {
      const res = await folderApi.list();
      // api 层已解包；这里再兜一层，保证列表一律是数组
      return unwrapOr<Folder[]>(res, []);
    },
    placeholderData: [],
  });
}

/** 获取文件夹内的文章 */
export function useFolderArticles(folderId: number | null, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['folders', folderId, 'articles', page, pageSize],
    queryFn: async () => {
      if (!folderId) return { items: [], total: 0, page: 1, page_size: pageSize };
      const res = await folderApi.listArticles(folderId, page, pageSize);
      return unwrapOr<FolderArticles>(res, {
        items: [],
        total: 0,
        page: 1,
        page_size: pageSize,
      });
    },
    enabled: !!folderId,
    placeholderData: { items: [], total: 0, page: 1, page_size: 20 },
  });
}

/** 创建文件夹 mutation */
export function useCreateFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; icon?: string; is_public?: boolean }) =>
      folderApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folders'] });
    },
  });
}

/** 更新文件夹 mutation */
export function useUpdateFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: number;
      name?: string;
      icon?: string;
      is_public?: boolean;
    }) => folderApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folders'] });
    },
  });
}

/** 删除文件夹 mutation */
export function useDeleteFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => folderApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folders'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}

/** 添加文章到文件夹 mutation */
export function useAddToFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ folderId, articleId }: { folderId: number; articleId: number }) =>
      folderApi.addArticle(folderId, articleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folders'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}

/** 从文件夹移除文章 mutation */
export function useRemoveFromFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ folderId, articleId }: { folderId: number; articleId: number }) =>
      folderApi.removeArticle(folderId, articleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folders'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}

/** 移动文章到另一个文件夹 mutation */
export function useMoveArticle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      articleId,
      fromFolderId,
      toFolderId,
    }: {
      articleId: number;
      fromFolderId: number;
      toFolderId: number;
    }) => folderApi.moveArticle(articleId, fromFolderId, toFolderId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folders'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}
