class ArticleDetailModel {
  const ArticleDetailModel({
    required this.id,
    required this.title,
    required this.description,
    required this.contentHtml,
    required this.author,
    required this.publishedAt,
    required this.image,
  });

  final int id;
  final String title;
  final String description;
  final String contentHtml;
  final String author;
  final String publishedAt;
  final String image;

  factory ArticleDetailModel.fromJson(Map<String, dynamic> json) {
    return ArticleDetailModel(
      id: (json['id'] as num?)?.toInt() ?? 0,
      title: (json['title'] ?? '') as String,
      description: (json['description'] ?? '') as String,
      contentHtml: (json['content'] ?? '') as String,
      author: (json['author'] ?? '') as String,
      publishedAt: (json['publish_date'] ?? json['created_at'] ?? '') as String,
      image: (json['thumb'] ?? json['image'] ?? '') as String,
    );
  }
}
