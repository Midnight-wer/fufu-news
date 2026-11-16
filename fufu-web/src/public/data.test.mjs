import assert from 'node:assert/strict';
import test from 'node:test';
import {
  getArticle,
  getHotArticles,
  normalizeSnapshot,
  queryArticles,
} from './data.ts';

const snapshot = {
  version: 1,
  generated_at: '2026-11-16T12:00:00Z',
  articles: [
    {
      id: 1,
      source_id: 1,
      title: 'AI 创作者工具发布',
      url: 'https://example.com/1',
      content: '<p>正文</p>',
      summary: '面向设计与创作者的全新工具',
      author: '作者甲',
      published_at: '2026-11-16T10:00:00Z',
      fetched_at: '2026-11-16T10:05:00Z',
      image_url: null,
      tags: ['AI', 'Design'],
      source_name: '示例科技',
      source_folder: '科技',
      view_count: 10,
    },
    {
      id: 2,
      source_id: 2,
      title: '独立游戏试玩报告',
      url: 'https://example.com/2',
      content: null,
      summary: '游戏战斗系统与关卡设计',
      author: null,
      published_at: '2026-11-12T10:00:00Z',
      fetched_at: '2026-11-12T10:05:00Z',
      image_url: null,
      tags: ['游戏'],
      source_name: '示例游戏',
      source_folder: '游戏',
      view_count: 20,
    },
    {
      id: 3,
      source_id: 1,
      title: '旧闻归档',
      url: 'https://example.com/3',
      content: null,
      summary: '历史文章',
      author: null,
      published_at: '2026-10-01T10:00:00Z',
      fetched_at: '2026-10-01T10:05:00Z',
      image_url: null,
      tags: [],
      source_name: '示例科技',
      source_folder: '科技',
      view_count: 30,
    },
  ],
  categories: [
    { name: '科技', count: 2 },
    { name: '游戏', count: 1 },
  ],
  hot: { day: [2, 1], week: [3], month: [] },
  hot_keywords: ['AI', '游戏'],
};

test('分类与时间筛选可以组合，结果按时间倒序', () => {
  const result = queryArticles(snapshot, { category: '科技', since: '7d' });
  assert.deepEqual(result.articles.map((article) => article.id), [1]);
  assert.equal(result.total, 1);
});

test('搜索支持多关键词、标签与来源，空关键词返回全部', () => {
  assert.deepEqual(
    queryArticles(snapshot, { query: '创作者 design' }).articles.map((article) => article.id),
    [1],
  );
  assert.deepEqual(
    queryArticles(snapshot, { query: '示例游戏' }).articles.map((article) => article.id),
    [2],
  );
  assert.equal(queryArticles(snapshot, { query: '  ' }).total, 3);
  assert.equal(queryArticles(snapshot, { query: '没有这条新闻' }).total, 0);
});

test('分页限制页码和每页数量，并返回总页数', () => {
  const lastPage = queryArticles(snapshot, { page: 99, pageSize: 2 });
  assert.equal(lastPage.page, 2);
  assert.equal(lastPage.totalPages, 2);
  assert.deepEqual(lastPage.articles.map((article) => article.id), [3]);

  const negativePage = queryArticles(snapshot, { page: -4, pageSize: 500 });
  assert.equal(negativePage.page, 1);
  assert.equal(negativePage.articles.length, 3);
});

test('详情与热榜只返回快照内有效文章', () => {
  assert.equal(getArticle(snapshot, 2)?.title, '独立游戏试玩报告');
  assert.equal(getArticle(snapshot, Number.NaN), undefined);
  assert.deepEqual(getHotArticles(snapshot, 'day').map((article) => article.id), [2, 1]);
  assert.deepEqual(getHotArticles(snapshot, 'month'), []);
});

test('损坏或空快照使用安全的空数据兜底', () => {
  const normalized = normalizeSnapshot({
    generated_at: 42,
    articles: [null, { id: '8', title: '有效标题', tags: '错误标签' }],
    categories: null,
    hot: { day: [8, 'bad'] },
  });
  assert.equal(normalized.generated_at, '');
  assert.equal(normalized.articles.length, 1);
  assert.equal(normalized.articles[0].id, 8);
  assert.deepEqual(normalized.articles[0].tags, []);
  assert.deepEqual(normalized.categories, []);
  assert.deepEqual(normalized.hot.day, [8]);
  assert.deepEqual(normalizeSnapshot(null).articles, []);
});
