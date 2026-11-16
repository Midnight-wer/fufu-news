import client from './client';
import { unwrap } from './unwrap';

export interface Folder {
  id: number;
  user_id: number;
  name: string;
  icon: string;
  is_public: boolean;
  sort_order: number;
  article_count: number;
  created_at: string;
}

export interface FolderArticles {
  items: any[];
  total: number;
  page: number;
  page_size: number;
}

// 后端 folders 端点同样是 { code, data, message } 信封，统一在 api 层解包。

export const folderApi = {
  /** 获取当前用户的所有文件夹 */
  list: () => client.get('/folders').then((r) => unwrap<Folder[]>(r.data)),

  /** 创建文件夹 */
  create: (data: { name: string; icon?: string; is_public?: boolean }) =>
    client.post('/folders', data).then((r) => unwrap<Folder>(r.data)),

  /** 更新文件夹 */
  update: (
    id: number,
    data: { name?: string; icon?: string; is_public?: boolean; sort_order?: number },
  ) => client.patch(`/folders/${id}`, data).then((r) => unwrap<Folder>(r.data)),

  /** 删除文件夹 */
  delete: (id: number) => client.delete(`/folders/${id}`).then((r) => unwrap(r.data)),

  /** 添加文章到文件夹 */
  addArticle: (folderId: number, articleId: number) =>
    client.post(`/folders/${folderId}/articles/${articleId}`).then((r) => unwrap(r.data)),

  /** 从文件夹移除文章 */
  removeArticle: (folderId: number, articleId: number) =>
    client.delete(`/folders/${folderId}/articles/${articleId}`).then((r) => unwrap(r.data)),

  /** 获取文件夹内的文章列表 */
  listArticles: (folderId: number, page = 1, pageSize = 20) =>
    client
      .get(`/folders/${folderId}/articles`, { params: { page, page_size: pageSize } })
      .then((r) => unwrap<FolderArticles>(r.data)),

  /** 移动文章到另一个文件夹 */
  moveArticle: (articleId: number, fromFolderId: number, toFolderId: number) =>
    client
      .post('/folders/move', {
        article_id: articleId,
        from_folder_id: fromFolderId,
        to_folder_id: toFolderId,
      })
      .then((r) => unwrap(r.data)),
};
