class ArticleModel {
  const ArticleModel({
    required this.id,
    required this.title,
    required this.description,
    required this.image,
    required this.author,
    required this.publishedAt,
    required this.categoryName,
  });

  final int id;
  final String title;
  final String description;
  final String image;
  final String author;
  final String publishedAt;
  final String categoryName;

  factory ArticleModel.fromJson(Map<String, dynamic> json) {
    return ArticleModel(
      id: (json['id'] as num?)?.toInt() ?? 0,
      title: (json['title'] ?? '') as String,
      description: (json['description'] ?? '') as String,
      image: (json['thumb'] ?? json['image'] ?? '') as String,
      author: (json['author'] ?? '') as String,
      publishedAt: (json['publish_date'] ?? json['created_at'] ?? '') as String,
      categoryName: (json['category_name'] ?? '') as String,
    );
  }
}
