import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, PencilSimple, TrashSimple, X, FolderSimple, Check, CaretDown } from '@phosphor-icons/react';
import { type Folder } from '../../api/folders';
import { useCreateFolder, useUpdateFolder, useDeleteFolder } from '../../hooks/useFolders';

const EMOJI_OPTIONS = [
  '📁', '💻', '🎮', '🎨', '🌸', '📰', '🌿', '💡',
  '❤️', '⭐', '📌', '🔥', '🎵', '📚', '🍰', '🎯',
  '✨', '💎', '🌈', '🎪',
];

interface FolderManagerProps {
  folders: Folder[];
  activeFolderId: number | null;
  onSelectFolder: (folderId: number | null) => void;
}

export default function FolderManager({ folders, activeFolderId, onSelectFolder }: FolderManagerProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newIcon, setNewIcon] = useState('📁');
  const [newPublic, setNewPublic] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [editingFolder, setEditingFolder] = useState<Folder | null>(null);
  const [editName, setEditName] = useState('');
  const [editIcon, setEditIcon] = useState('📁');
  const [showEditEmojiPicker, setShowEditEmojiPicker] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<Folder | null>(null);

  const createFolder = useCreateFolder();
  const updateFolder = useUpdateFolder();
  const deleteFolder = useDeleteFolder();

  const emojiRef = useRef<HTMLDivElement>(null);
  const editEmojiRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭 emoji picker
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (emojiRef.current && !emojiRef.current.contains(e.target as Node)) {
        setShowEmojiPicker(false);
      }
      if (editEmojiRef.current && !editEmojiRef.current.contains(e.target as Node)) {
        setShowEditEmojiPicker(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleCreate = () => {
    if (!newName.trim()) return;
    createFolder.mutate(
      { name: newName.trim(), icon: newIcon, is_public: newPublic },
      {
        onSuccess: () => {
          setNewName('');
          setNewIcon('📁');
          setNewPublic(false);
          setShowCreate(false);
        },
      }
    );
  };

  const handleRename = () => {
    if (!editingFolder || !editName.trim()) return;
    updateFolder.mutate(
      { id: editingFolder.id, name: editName.trim(), icon: editIcon },
      {
        onSuccess: () => {
          setEditingFolder(null);
          setEditName('');
          setEditIcon('📁');
        },
      }
    );
  };

  const handleDelete = () => {
    if (!deleteConfirm) return;
    deleteFolder.mutate(deleteConfirm.id, {
      onSuccess: () => {
        setDeleteConfirm(null);
        if (activeFolderId === deleteConfirm.id) {
          onSelectFolder(null);
        }
      },
    });
  };

  const openEdit = (folder: Folder) => {
    setEditingFolder(folder);
    setEditName(folder.name);
    setEditIcon(folder.icon);
    setShowEditEmojiPicker(false);
  };

  return (
    <div className="mb-6">
      {/* 文件夹标签栏 */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {/* 全部收藏 */}
        <button
          onClick={() => onSelectFolder(null)}
          className={`flex-shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-fufu-btn font-cute text-sm transition-all border-2 ${
            activeFolderId === null
              ? 'border-fufu-pink bg-fufu-pink-soft/20 text-fufu-pink shadow-fufu'
              : 'border-transparent bg-white text-fufu-text-muted hover:text-fufu-text hover:bg-fufu-cream'
          }`}
        >
          <FolderSimple size={16} />
          全部收藏
        </button>

        {/* 文件夹标签 */}
        <AnimatePresence>
          {folders.map((folder) => (
            <motion.button
              key={folder.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.2 }}
              onClick={() => onSelectFolder(folder.id)}
              onDoubleClick={() => openEdit(folder)}
              onContextMenu={(e) => { e.preventDefault(); openEdit(folder); }}
              className={`flex-shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-fufu-btn font-cute text-sm transition-all border-2 group relative ${
                activeFolderId === folder.id
                  ? 'border-fufu-teal bg-fufu-teal-soft/10 text-fufu-teal-deep shadow-fufu'
                  : 'border-transparent bg-white text-fufu-text-muted hover:text-fufu-text hover:bg-fufu-cream'
              }`}
            >
              <span className="text-base">{folder.icon}</span>
              <span>{folder.name}</span>
              <span className="text-xs opacity-50 font-body">({folder.article_count})</span>
              {/* 编辑小按钮 */}
              <span
                onClick={(e) => { e.stopPropagation(); openEdit(folder); }}
                className="ml-0.5 opacity-0 group-hover:opacity-100 transition-opacity text-fufu-text-muted hover:text-fufu-teal"
              >
                <PencilSimple size={12} />
              </span>
            </motion.button>
          ))}
        </AnimatePresence>

        {/* 新建文件夹按钮 */}
        <button
          onClick={() => setShowCreate(true)}
          className="flex-shrink-0 flex items-center gap-1 px-4 py-2 rounded-fufu-btn font-cute text-sm border-2 border-dashed border-fufu-text-muted/30 text-fufu-text-muted hover:text-fufu-teal hover:border-fufu-teal/40 transition-all bg-transparent"
        >
          <Plus size={16} />
          新建文件夹
        </button>
      </div>

      {/* ===== 创建文件夹弹窗 ===== */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm"
            onClick={() => setShowCreate(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-fufu-modal shadow-fufu-float p-6 w-full max-w-sm mx-4 border border-fufu-highlight/30"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-cute text-lg text-fufu-text">📁 新建文件夹</h3>
                <button onClick={() => setShowCreate(false)} className="text-fufu-text-muted hover:text-fufu-pink transition-colors">
                  <X size={20} />
                </button>
              </div>

              {/* 名称输入 */}
              <label className="block font-body text-sm text-fufu-text-light mb-1.5">文件夹名称</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                placeholder="如：科技收藏"
                className="w-full px-4 py-2.5 rounded-fufu-input border border-fufu-highlight/50 bg-fufu-cream-soft text-fufu-text font-body text-sm placeholder:text-fufu-text-muted/50 focus:outline-none focus:border-fufu-teal focus:ring-2 focus:ring-fufu-teal/10 transition-all"
                autoFocus
              />

              {/* 图标选择 */}
              <label className="block font-body text-sm text-fufu-text-light mb-1.5 mt-4">文件夹图标</label>
              <div ref={emojiRef} className="relative">
                <button
                  onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-fufu-input border border-fufu-highlight/50 bg-fufu-cream-soft text-fufu-text font-body text-sm hover:border-fufu-teal/50 transition-all"
                >
                  <span className="text-xl">{newIcon}</span>
                  <span className="text-fufu-text-muted">选择图标</span>
                  <CaretDown size={14} className="ml-auto text-fufu-text-muted" />
                </button>
                {showEmojiPicker && (
                  <div className="absolute top-full mt-1 left-0 bg-white rounded-fufu shadow-fufu-float border border-fufu-highlight/30 p-2 grid grid-cols-5 gap-1.5 z-10">
                    {EMOJI_OPTIONS.map((emoji) => (
                      <button
                        key={emoji}
                        onClick={() => { setNewIcon(emoji); setShowEmojiPicker(false); }}
                        className={`w-10 h-10 flex items-center justify-center rounded-fufu text-lg transition-all ${
                          newIcon === emoji ? 'bg-fufu-teal-soft/20 ring-2 ring-fufu-teal/30' : 'hover:bg-fufu-cream'
                        }`}
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* 公开/私密切换 */}
              <label className="flex items-center justify-between mt-4 py-2">
                <span className="font-body text-sm text-fufu-text">公开文件夹</span>
                <button
                  onClick={() => setNewPublic(!newPublic)}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    newPublic ? 'bg-fufu-teal' : 'bg-fufu-text-muted/30'
                  }`}
                >
                  <motion.div
                    animate={{ x: newPublic ? 20 : 2 }}
                    className="absolute top-1 w-4 h-4 bg-white rounded-full shadow"
                  />
                </button>
              </label>

              {/* 操作按钮 */}
              <div className="flex items-center justify-end gap-3 mt-5">
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 rounded-fufu-btn font-cute text-sm text-fufu-text-light hover:bg-fufu-cream transition-all"
                >
                  取消
                </button>
                <button
                  onClick={handleCreate}
                  disabled={!newName.trim() || createFolder.isPending}
                  className="fufu-btn-primary px-5 py-2 rounded-fufu-btn font-cute text-sm disabled:opacity-40 transition-all"
                >
                  {createFolder.isPending ? '创建中...' : '创建'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ===== 编辑/重命名文件夹弹窗 ===== */}
      <AnimatePresence>
        {editingFolder && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm"
            onClick={() => setEditingFolder(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-fufu-modal shadow-fufu-float p-6 w-full max-w-sm mx-4 border border-fufu-highlight/30"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-cute text-lg text-fufu-text">✏️ 编辑文件夹</h3>
                <button onClick={() => setEditingFolder(null)} className="text-fufu-text-muted hover:text-fufu-pink transition-colors">
                  <X size={20} />
                </button>
              </div>

              {/* 名称 */}
              <label className="block font-body text-sm text-fufu-text-light mb-1.5">文件夹名称</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleRename()}
                className="w-full px-4 py-2.5 rounded-fufu-input border border-fufu-highlight/50 bg-fufu-cream-soft text-fufu-text font-body text-sm placeholder:text-fufu-text-muted/50 focus:outline-none focus:border-fufu-teal focus:ring-2 focus:ring-fufu-teal/10 transition-all"
                autoFocus
              />

              {/* 图标 */}
              <label className="block font-body text-sm text-fufu-text-light mb-1.5 mt-4">图标</label>
              <div ref={editEmojiRef} className="relative">
                <button
                  onClick={() => setShowEditEmojiPicker(!showEditEmojiPicker)}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-fufu-input border border-fufu-highlight/50 bg-fufu-cream-soft text-fufu-text font-body text-sm hover:border-fufu-teal/50 transition-all"
                >
                  <span className="text-xl">{editIcon}</span>
                  <span className="text-fufu-text-muted">选择图标</span>
                  <CaretDown size={14} className="ml-auto text-fufu-text-muted" />
                </button>
                {showEditEmojiPicker && (
                  <div className="absolute top-full mt-1 left-0 bg-white rounded-fufu shadow-fufu-float border border-fufu-highlight/30 p-2 grid grid-cols-5 gap-1.5 z-10">
                    {EMOJI_OPTIONS.map((emoji) => (
                      <button
                        key={emoji}
                        onClick={() => { setEditIcon(emoji); setShowEditEmojiPicker(false); }}
                        className={`w-10 h-10 flex items-center justify-center rounded-fufu text-lg transition-all ${
                          editIcon === emoji ? 'bg-fufu-teal-soft/20 ring-2 ring-fufu-teal/30' : 'hover:bg-fufu-cream'
                        }`}
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* 删除按钮 */}
              <button
                onClick={() => { setEditingFolder(null); setDeleteConfirm(editingFolder); }}
                className="flex items-center gap-2 mt-5 px-4 py-2 rounded-fufu-btn font-cute text-sm text-fufu-error bg-fufu-error-light/20 hover:bg-fufu-error-light/40 transition-all"
              >
                <TrashSimple size={16} />
                删除此文件夹
              </button>

              {/* 操作按钮 */}
              <div className="flex items-center justify-end gap-3 mt-4">
                <button
                  onClick={() => setEditingFolder(null)}
                  className="px-4 py-2 rounded-fufu-btn font-cute text-sm text-fufu-text-light hover:bg-fufu-cream transition-all"
                >
                  取消
                </button>
                <button
                  onClick={handleRename}
                  disabled={!editName.trim() || updateFolder.isPending}
                  className="fufu-btn-primary px-5 py-2 rounded-fufu-btn font-cute text-sm disabled:opacity-40 transition-all"
                >
                  {updateFolder.isPending ? '保存中...' : '保存'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ===== 删除确认弹窗 ===== */}
      <AnimatePresence>
        {deleteConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm"
            onClick={() => setDeleteConfirm(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-fufu-modal shadow-fufu-float p-6 w-full max-w-sm mx-4 border border-fufu-highlight/30"
            >
              <p className="text-5xl text-center mb-4">🗑️</p>
              <h3 className="font-cute text-lg text-fufu-text text-center">确定要删除吗？</h3>
              <p className="font-body text-sm text-fufu-text-light text-center mt-2 leading-relaxed">
                删除文件夹 <span className="text-fufu-pink font-cute">{deleteConfirm.icon} {deleteConfirm.name}</span> 后，
                里面的文章不会被删除，只是取消分类哦～
              </p>
              <div className="flex items-center justify-center gap-3 mt-5">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="px-5 py-2 rounded-fufu-btn font-cute text-sm text-fufu-text-light bg-fufu-cream hover:bg-fufu-highlight/30 transition-all"
                >
                  取消
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleteFolder.isPending}
                  className="px-5 py-2 rounded-fufu-btn font-cute text-sm bg-fufu-error text-white hover:bg-fufu-error/80 disabled:opacity-40 transition-all"
                >
                  {deleteFolder.isPending ? '删除中...' : '确认删除'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
