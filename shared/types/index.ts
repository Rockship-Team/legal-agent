import { z } from 'zod';

// User types
export const UserRoleSchema = z.enum(['USER', 'ADMIN']);
export type UserRole = z.infer<typeof UserRoleSchema>;

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().min(2).max(255),
  role: UserRoleSchema,
  createdAt: z.string().datetime(),
});
export type User = z.infer<typeof UserSchema>;

// Auth types
export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});
export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export const RegisterRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().min(2).max(255),
});
export type RegisterRequest = z.infer<typeof RegisterRequestSchema>;

export const AuthResponseSchema = z.object({
  user: UserSchema,
  token: z.string(),
  expiresAt: z.string().datetime(),
});
export type AuthResponse = z.infer<typeof AuthResponseSchema>;

// Conversation types
export const ConversationStatusSchema = z.enum(['ACTIVE', 'ARCHIVED']);
export type ConversationStatus = z.infer<typeof ConversationStatusSchema>;

export const ConversationSchema = z.object({
  id: z.string().uuid(),
  title: z.string().max(255).nullable(),
  status: ConversationStatusSchema,
  metadata: z.record(z.unknown()).optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});
export type Conversation = z.infer<typeof ConversationSchema>;

// Message types
export const MessageRoleSchema = z.enum(['USER', 'ASSISTANT', 'SYSTEM']);
export type MessageRole = z.infer<typeof MessageRoleSchema>;

export const CitationSchema = z.object({
  id: z.string().uuid(),
  documentTitle: z.string(),
  documentNumber: z.string().nullable(),
  articleNumber: z.string().nullable(),
  excerpt: z.string().nullable(),
  relevanceScore: z.number().min(0).max(1),
  effectiveDate: z.string().nullable(),
  status: z.enum(['active', 'amended', 'repealed']),
});
export type Citation = z.infer<typeof CitationSchema>;

export const MessageSchema = z.object({
  id: z.string().uuid(),
  role: MessageRoleSchema,
  content: z.string(),
  citations: z.array(CitationSchema).optional(),
  createdAt: z.string().datetime(),
});
export type Message = z.infer<typeof MessageSchema>;

export const SendMessageRequestSchema = z.object({
  content: z.string().min(1).max(10000),
});
export type SendMessageRequest = z.infer<typeof SendMessageRequestSchema>;

export const MessageResponseSchema = z.object({
  userMessage: MessageSchema,
  assistantMessage: MessageSchema,
  disclaimer: z.string(),
});
export type MessageResponse = z.infer<typeof MessageResponseSchema>;

// Legal Document types
export const LegalDocumentCategorySchema = z.enum([
  'LAW',
  'DECREE',
  'CIRCULAR',
  'RESOLUTION',
  'DECISION',
  'TEMPLATE',
]);
export type LegalDocumentCategory = z.infer<typeof LegalDocumentCategorySchema>;

export const LegalDocumentStatusSchema = z.enum(['ACTIVE', 'AMENDED', 'REPEALED']);
export type LegalDocumentStatus = z.infer<typeof LegalDocumentStatusSchema>;

export const LegalDocumentSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  documentNumber: z.string().nullable(),
  category: LegalDocumentCategorySchema,
  effectiveDate: z.string().nullable(),
  status: LegalDocumentStatusSchema,
  content: z.string().optional(),
  metadata: z.record(z.unknown()).optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});
export type LegalDocument = z.infer<typeof LegalDocumentSchema>;

// Search types
export const SearchResultSchema = z.object({
  documentId: z.string().uuid(),
  title: z.string(),
  documentNumber: z.string().nullable(),
  category: z.string(),
  excerpt: z.string(),
  relevanceScore: z.number(),
  effectiveDate: z.string().nullable(),
  status: LegalDocumentStatusSchema,
});
export type SearchResult = z.infer<typeof SearchResultSchema>;

export const SearchRequestSchema = z.object({
  query: z.string().min(3).max(1000),
  category: LegalDocumentCategorySchema.optional(),
  status: LegalDocumentStatusSchema.optional().default('ACTIVE'),
  limit: z.number().int().min(1).max(50).optional().default(10),
  minRelevance: z.number().min(0).max(1).optional().default(0.6),
});
export type SearchRequest = z.infer<typeof SearchRequestSchema>;

// Document Template types
export const DocumentTemplateCategorySchema = z.enum([
  'RENTAL',
  'EMPLOYMENT',
  'SALE',
  'SERVICE',
  'LOAN',
]);
export type DocumentTemplateCategory = z.infer<typeof DocumentTemplateCategorySchema>;

export const TemplateFieldSchema = z.object({
  name: z.string(),
  type: z.enum(['string', 'number', 'date', 'boolean']),
  label: z.string(),
});
export type TemplateField = z.infer<typeof TemplateFieldSchema>;

export const DocumentTemplateSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  category: DocumentTemplateCategorySchema,
  requiredFields: z.array(TemplateFieldSchema),
  optionalFields: z.array(TemplateFieldSchema).optional(),
  version: z.string(),
});
export type DocumentTemplate = z.infer<typeof DocumentTemplateSchema>;

// Generated Document types
export const GeneratedDocumentStatusSchema = z.enum(['DRAFT', 'FINALIZED']);
export type GeneratedDocumentStatus = z.infer<typeof GeneratedDocumentStatusSchema>;

export const DocumentFormatSchema = z.enum(['PDF', 'DOCX']);
export type DocumentFormat = z.infer<typeof DocumentFormatSchema>;

export const GeneratedDocumentSchema = z.object({
  id: z.string().uuid(),
  templateId: z.string().uuid(),
  templateName: z.string(),
  status: GeneratedDocumentStatusSchema,
  format: DocumentFormatSchema,
  variables: z.record(z.unknown()),
  createdAt: z.string().datetime(),
  downloadUrl: z.string().url().optional(),
});
export type GeneratedDocument = z.infer<typeof GeneratedDocumentSchema>;

export const GenerateDocumentRequestSchema = z.object({
  templateId: z.string().uuid(),
  conversationId: z.string().uuid().optional(),
  variables: z.record(z.unknown()),
  format: DocumentFormatSchema.optional().default('PDF'),
});
export type GenerateDocumentRequest = z.infer<typeof GenerateDocumentRequestSchema>;

// API Response types
export const PaginatedResponseSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    data: z.array(itemSchema),
    total: z.number().int(),
    limit: z.number().int(),
    offset: z.number().int(),
  });

export const ErrorResponseSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.record(z.unknown()).optional(),
});
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
